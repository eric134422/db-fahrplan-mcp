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

# The API ships delay/quality reasons as bare numeric codes; the texts are not
# part of the spec. Mapping reverse-engineered by the Travel::Status::DE::IRIS
# project (github.com/derf/Travel-Status-DE-IRIS, lib/.../Result.pm).
MESSAGE_CODES = {
    1: "Nähere Informationen in Kürze",
    2: "Polizeieinsatz",
    3: "Feuerwehreinsatz auf der Strecke",
    4: "Kurzfristiger Personalausfall",
    5: "Ärztliche Versorgung eines Fahrgastes",
    6: "Betätigen der Notbremse",
    7: "Unbefugte Personen auf der Strecke",
    8: "Notarzteinsatz auf der Strecke",
    9: "Streikauswirkungen",
    10: "Tiere auf der Strecke",
    11: "Unwetter",
    12: "Warten auf ein verspätetes Schiff",
    13: "Pass- und Zollkontrolle",
    14: "Defekt am Bahnhof",
    15: "Beeinträchtigung durch Vandalismus",
    16: "Entschärfung einer Fliegerbombe",
    17: "Beschädigung einer Brücke",
    18: "Umgestürzter Baum auf der Strecke",
    19: "Unfall an einem Bahnübergang",
    20: "Tiere im Gleis",
    21: "Warten auf Anschlussreisende",
    22: "Witterungsbedingte Beeinträchtigungen",
    23: "Betriebsstabilisierung",
    24: "Verspätung im Ausland",
    25: "Bereitstellung weiterer Wagen",
    26: "Abhängen von Wagen",
    27: "Technische Störung am Bus",
    28: "Gegenstände auf der Strecke",
    29: "Ersatzverkehr mit Bus ist eingerichtet",
    30: "Personalausfall im Stellwerk",
    31: "Bauarbeiten",
    32: "Längere Haltezeit am Bahnhof",
    33: "Defekt an der Oberleitung",
    34: "Defekt an einem Signal",
    35: "Streckensperrung",
    36: "Technische Störung am Zug",
    37: "Kurzfristiger Fahrzeugausfall",
    38: "Defekt an der Strecke",
    39: "Stau / Hohes Verkehrsaufkommen",
    40: "Defektes Stellwerk",
    41: "Defekt an einem Bahnübergang",
    42: "Außerplanmäßige Geschwindigkeitsbeschränkung",
    43: "Verspätung eines vorausfahrenden Zuges",
    44: "Warten auf einen entgegenkommenden Zug",
    45: "Vorfahrt eines anderen Zuges",
    46: "Vorfahrt eines anderen Zuges",
    47: "Verspätete Bereitstellung",
    48: "Verspätung aus vorheriger Fahrt",
    49: "Kurzfristiger Personalausfall",
    50: "Kurzfristige Erkrankung von Personal",
    51: "Verspätetes Personal aus vorheriger Fahrt",
    52: "Streik",
    53: "Unwetterauswirkungen",
    54: "Verfügbarkeit der Gleise derzeit eingeschränkt",
    55: "Technischer Defekt an einem anderen Zug",
    56: "Laden der Antriebsbatterie",
    57: "Zusätzlicher Halt",
    58: "Umleitung",
    59: "Schnee und Eis",
    60: "Witterungsbedingt verminderte Geschwindigkeit",
    61: "Defekte Tür",
    62: "Behobener Defekt am Zug",
    63: "Technische Untersuchung am Zug",
    64: "Defekt an einer Weiche",
    65: "Erdrutsch",
    66: "Hochwasser",
    67: "Behördliche Maßnahme",
    68: "Hohes Fahrgastaufkommen",
    69: "Zug verkehrt mit verminderter Geschwindigkeit",
    70: "WLAN nicht verfügbar",
    71: "Eingeschränktes WLAN",
    72: "Info/Entertainment nicht verfügbar",
    73: "Heute: Mehrzweckabteil vorne",
    74: "Heute: Mehrzweckabteil hinten",
    75: "Heute: 1. Klasse vorne",
    76: "Heute: 1. Klasse hinten",
    77: "1. Klasse fehlt",
    78: "Ersatzverkehr mit Bus ist eingerichtet",
    79: "Mehrzweckabteil fehlt",
    80: "Abweichende Wagenreihung",
    81: "Fahrzeugtausch",
    82: "Mehrere Wagen fehlen",
    83: "Heute ohne fahrzeuggebundene Einstiegshilfe",
    84: "Zug verkehrt richtig gereiht",
    85: "Ein Wagen fehlt",
    86: "Gesamter Zug ohne Reservierung",
    87: "Einzelne Wagen ohne Reservierung",
    88: "Keine Qualitätsmängel",
    89: "Reservierungen sind wieder vorhanden",
    90: "Kein gastronomisches Angebot",
    91: "Fahrradmitnahme nicht möglich",
    92: "Fahrradmitnahme kann nicht garantiert werden",
    93: "Behindertengerechte Einrichtung fehlt",
    94: "Ersatzbewirtschaftung",
    95: "Universaltoilette fehlt",
    96: "Zustieg kann nicht garantiert werden",
    97: "Hohe Auslastung",
    98: "Sonstige Qualitätsmängel",
    99: "Verzögerungen im Betriebsablauf",
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


def _parse_message(m: ElementTree.Element) -> dict:
    """Parse a single <m> element into a readable dict."""
    code = m.get("c")
    code = int(code) if code and code.lstrip("-").isdigit() else None
    message = {
        "type": MESSAGE_TYPES.get(m.get("t") or "", m.get("t")),
        "code": code,
        "reason": MESSAGE_CODES.get(code) if code is not None else None,
        "category": m.get("cat"),
        "priority": m.get("pr"),
        "valid_from": _iso(m.get("from")),
        "valid_to": _iso(m.get("to")),
        "timestamp": _iso(m.get("ts")),
        # Rarely populated, but free text beats a code when it is there.
        "text": m.get("ext") or m.get("int"),
        "link": m.get("elnk"),
        "id": m.get("id"),
    }
    return {k: v for k, v in message.items() if v is not None}


def _message_key(message: dict) -> tuple:
    """Identity of a message by content, not by id.

    The same reason is often repeated under several message ids, so the id
    is useless for deduplication; the same reason at the same timestamp is.
    """
    return (
        message.get("type"),
        message.get("code"),
        message.get("category"),
        message.get("timestamp"),
    )


def _parse_messages(elements: list[ElementTree.Element]) -> list[dict]:
    """Parse <m> elements, dropping the duplicates the feed is full of."""
    messages, seen = [], set()
    for m in elements:
        message = _parse_message(m)
        key = _message_key(message)
        if key in seen:
            continue
        seen.add(key)
        messages.append(message)
    return messages


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
        # Cause-of-delay and quality messages hang off the event, not the
        # stop - collecting only the stop's own <m> children misses them.
        "messages": _parse_messages(el.findall("m")) or None,
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

    messages = _parse_messages(s.findall("m"))

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


def _iso_delay(planned: str | None, changed: str | None) -> int | None:
    if not planned or not changed:
        return None
    try:
        pt = datetime.strptime(planned, "%Y-%m-%dT%H:%M")
        ct = datetime.strptime(changed, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None
    return int((ct - pt).total_seconds() // 60)


def _merge_messages(planned: list | None, changes: list | None) -> list:
    """Union the /plan and /fchg message lists - neither is a superset."""
    merged, seen = [], set()
    for message in (planned or []) + (changes or []):
        key = _message_key(message)
        if key in seen:
            continue
        seen.add(key)
        merged.append(message)
    return merged


def merge_changes(
    planned: dict,
    changes: dict,
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict:
    """Overlay /fchg change data onto a /plan timetable, joined by stop id.

    The /fchg feed carries only the delta (changed time/platform/status),
    so delays are computed here against the planned times. Added trips
    (e.g. replacement buses) that fall inside the [window_start, window_end)
    ISO-time window are appended, since they exist only in the changes feed.
    """
    changed_by_id = {s["id"]: s for s in changes.get("stops", [])}

    for stop in planned.get("stops", []):
        change = changed_by_id.pop(stop.get("id"), None)
        if not change:
            continue
        for name in ("arrival", "departure"):
            changed_event = change.get(name)
            if not changed_event:
                continue
            event = stop.get(name)
            if event is None:
                stop[name] = changed_event
                continue
            for key in ("changed_time", "changed_platform", "status"):
                if key in changed_event:
                    event[key] = changed_event[key]
            delay = _iso_delay(event.get("planned_time"), event.get("changed_time"))
            if delay is not None:
                event["delay_minutes"] = delay
            merged = _merge_messages(event.get("messages"), changed_event.get("messages"))
            if merged:
                event["messages"] = merged
        merged = _merge_messages(stop.get("messages"), change.get("messages"))
        if merged:
            stop["messages"] = merged

    # Trips that exist only in the changes feed (added stops, replacement
    # buses) have no planned counterpart to join with - include the ones
    # that fall inside the requested hour slice.
    if window_start and window_end:
        for stop in changed_by_id.values():
            time = _sort_key(stop)
            if window_start <= time < window_end:
                planned["stops"].append(stop)

    planned["stops"].sort(key=_sort_key)
    return planned


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
