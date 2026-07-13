"""Thin HTTP client for the Deutsche Bahn Timetables API."""

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

BASE_URL = "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1"
CLIENT_ID = os.getenv("DB_TIMETABLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("DB_TIMETABLE_CLIENT_SECRET", "")


class ApiError(Exception):
    """Raised when the DB API responds with an error."""


async def fetch(endpoint: str) -> str:
    """GET an endpoint and return the raw XML body.

    Args:
        endpoint: path below the base URL, e.g. "/station/Aachen Hbf"
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        raise ApiError(
            "Missing credentials: set DB_TIMETABLE_CLIENT_ID and "
            "DB_TIMETABLE_CLIENT_SECRET in .env (see .env.example)"
        )

    headers = {
        "DB-Client-Id": CLIENT_ID,
        "DB-Api-Key": CLIENT_SECRET,
        "Accept": "application/xml",
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}{endpoint}", headers=headers, timeout=30.0
        )
        if response.status_code == 404:
            raise ApiError(f"Not found: {endpoint} (unknown station or time slice?)")
        if response.status_code in (401, 403):
            raise ApiError("Authentication failed - check your API credentials")
        if response.status_code >= 400:
            raise ApiError(
                f"API error {response.status_code} for {endpoint} - "
                "check EVA number and parameter formats"
            )
        return response.text
