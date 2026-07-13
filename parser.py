"""Parse the DB Timetables API XML into compact, readable dicts.

Attribute names follow the official OpenAPI spec ("Timetables" v1):
pt/ct = planned/changed time, pp/cp = planned/changed platform,
ppth = planned path, tl = trip label, ps/cs = planned/changed status.
"""

from datetime import datetime
from xml.etree import ElementTree

EVENT_STATUS = {"p": "planned", "a": "added", "c": "cancelled"}

MESSAGE_TYPES = {
    "h": "him",
    "q": "quality-change",
    "f": "free-text",
    "d": "cause-of-delay",
    "i": "ibis",
    "u": "unassigned-ibis",
    "r": "disruption",
    "c": "connection",
}


def _iso(ts: str | None) -> str | None:
    """'2607131447' (YYMMddHHmm) -> '2026-07-13T14:47'."""
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%y%m%d%H%M").strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        return ts


def _delay_minutes(planned: str | None, changed: str | None) -> int | None:
    if not planned or not changed:
        return None
    try:
        pt = datetime.strptime(planned, "%y%m%d%H%M")
        ct = datetime.strptime(changed, "%y%m%d%H%M")
    except ValueError:
        return None
    return int((ct - pt).total_seconds() // 60)


def _parse_event(el: ElementTree.Element | None) -> dict | None:
    """Parse an <ar> or <dp> event element."""
    if el is None:
        return None
    pt, ct = el.get("pt"), el.get("ct")
    event = {
        "planned_time": _iso(pt),
        "changed_time": _iso(ct),
        "delay_minutes": _delay_minutes(pt, ct),
        "platform": el.get("pp"),
        "changed_platform": el.get("cp"),
        "line": el.get("l"),
        "status": EVENT_STATUS.get(el.get("cs") or el.get("ps") or ""),
        "_path": el.get("ppth"),
    }
    return {k: v for k, v in event.items() if v is not None}


def _parse_stop(s: ElementTree.Element) -> dict:
    tl = s.find("tl")
    arrival = _parse_event(s.find("ar"))
    departure = _parse_event(s.find("dp"))

    # The path never includes the current station: for arrivals its first
    # entry is the trip's origin, for departures its last is the destination.
    if arrival:
        path = arrival.pop("_path", None)
        if path:
            arrival["origin"] = path.split("|")[0]
    if departure:
        path = departure.pop("_path", None)
        if path:
            departure["destination"] = path.split("|")[-1]

    line = (arrival or {}).get("line") or (departure or {}).get("line")
    for event in (arrival, departure):
        if event:
            event.pop("line", None)

    messages = [
        {
            "type": MESSAGE_TYPES.get(m.get("t") or "", m.get("t")),
            "priority": m.get("pr"),
        }
        for m in s.findall("m")
    ]

    stop = {
        "id": s.get("id"),
        "train": f"{tl.get('c')} {tl.get('n')}" if tl is not None else None,
        "line": line,
        "arrival": arrival,
        "departure": departure,
        "messages": messages or None,
    }
    return {k: v for k, v in stop.items() if v is not None}


def _sort_key(stop: dict) -> str:
    for event_name in ("departure", "arrival"):
        event = stop.get(event_name) or {}
        time = event.get("changed_time") or event.get("planned_time")
        if time:
            return time
    return "9999"


def parse_timetable(xml_text: str) -> dict:
    """Parse a <timetable> response (/plan, /fchg, /rchg) into a dict."""
    root = ElementTree.fromstring(xml_text)
    stops = sorted((_parse_stop(s) for s in root.findall("s")), key=_sort_key)
    timetable = {
        "station": root.get("station"),
        "eva": root.get("eva"),
        "stops": stops,
    }
    return {k: v for k, v in timetable.items() if v is not None}


def parse_stations(xml_text: str) -> list[dict]:
    """Parse a <stations> response (/station) into a list of dicts."""
    root = ElementTree.fromstring(xml_text)
    stations = []
    for station in root.findall("station"):
        entry = {
            "name": station.get("name"),
            "eva": station.get("eva"),
            "ds100": station.get("ds100"),
            "platforms": (station.get("p") or "").split("|") or None,
        }
        stations.append({k: v for k, v in entry.items() if v})
    return stations
