"""MCP server for the Deutsche Bahn Timetables API.

Exposes station search, planned departures, and live changes as MCP tools.
All tools return compact JSON parsed from the API's XML responses.
"""

import json
from datetime import datetime
from urllib.parse import quote

from mcp.server.fastmcp import FastMCP

from api import ApiError, fetch
from parser import parse_stations, parse_timetable

mcp = FastMCP("DB Fahrplan")


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False)


@mcp.tool()
async def find_station(pattern: str) -> str:
    """Search German train stations and get their EVA numbers.

    Args:
        pattern: Station name, EVA number, or DS100 code. Prefix search -
            exact DB naming works best (e.g. "Stolberg(Rheinl)Hbf" rather
            than "Stolberg Hbf"). Umlauts often fail; try "*" as wildcard.
    """
    try:
        xml = await fetch(f"/station/{quote(pattern)}")
    except ApiError as e:
        return _json({"error": str(e)})
    stations = parse_stations(xml)
    if not stations:
        return _json({"error": f"No stations match '{pattern}'. Try a shorter prefix or a wildcard like '{pattern}*'."})
    return _json(stations)


@mcp.tool()
async def get_departures(eva_no: str, date: str | None = None, hour: str | None = None) -> str:
    """Get the planned timetable for a station within one hour slice.

    Static planned data (no delays - combine with get_live_changes for
    real-time info). Defaults to the current date and hour.

    Args:
        eva_no: EVA number of the station (e.g. "8000001" for Aachen Hbf).
            Use find_station to look it up.
        date: Day in YYMMDD format (e.g. "260713"). Defaults to today.
        hour: Hour in HH format, 00-23. Defaults to the current hour.
    """
    now = datetime.now()
    date = date or now.strftime("%y%m%d")
    hour = hour or now.strftime("%H")
    try:
        xml = await fetch(f"/plan/{quote(eva_no)}/{quote(date)}/{quote(hour)}")
    except ApiError as e:
        return _json({"error": str(e)})
    return _json(parse_timetable(xml))


@mcp.tool()
async def get_live_changes(eva_no: str, limit: int = 30) -> str:
    """Get all known real-time changes for a station: delays, platform
    changes, cancellations. Covers the current operating day.

    Args:
        eva_no: EVA number of the station (e.g. "8000001" for Aachen Hbf).
        limit: Maximum number of stops to return (sorted by time).
    """
    try:
        xml = await fetch(f"/fchg/{quote(eva_no)}")
    except ApiError as e:
        return _json({"error": str(e)})
    timetable = parse_timetable(xml)
    total = len(timetable["stops"])
    timetable["stops"] = timetable["stops"][:limit]
    timetable["total_stops_with_changes"] = total
    return _json(timetable)


@mcp.tool()
async def get_recent_changes(eva_no: str, limit: int = 30) -> str:
    """Get only the changes of the last 2 minutes for a station.
    Much smaller than get_live_changes - use for frequent polling.

    Args:
        eva_no: EVA number of the station (e.g. "8000001" for Aachen Hbf).
        limit: Maximum number of stops to return (sorted by time).
    """
    try:
        xml = await fetch(f"/rchg/{quote(eva_no)}")
    except ApiError as e:
        return _json({"error": str(e)})
    timetable = parse_timetable(xml)
    total = len(timetable["stops"])
    timetable["stops"] = timetable["stops"][:limit]
    timetable["total_stops_with_changes"] = total
    return _json(timetable)


if __name__ == "__main__":
    mcp.run(transport="stdio")
