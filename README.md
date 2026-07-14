# db-fahrplan-mcp

An (unofficial) MCP server for the [Deutsche Bahn Timetables API](https://developers.deutschebahn.com/db-api-marketplace/apis/product/timetables) - station search, planned departures and real-time changes (delays, platform changes, cancellations) as tools for Claude and other MCP hosts.

Written in Python with [FastMCP](https://github.com/modelcontextprotocol/python-sdk). The API's XML responses are parsed into compact JSON server-side, so tool outputs stay small and readable for the model.

## Tools

| Tool | API endpoint | Description |
|---|---|---|
| `find_station` | `/station/{pattern}` | Search stations by name, EVA number, or DS100 code |
| `get_departures` | `/plan/…` + `/fchg/…` (merged) | Timetable for one hour slice (defaults to now), with real-time data: delays, platform changes, cancellations, added trips |
| `get_live_changes` | `/fchg/{eva}` | All known real-time changes for the current day |
| `get_recent_changes` | `/rchg/{eva}` | Only changes from the last 2 minutes (cheap polling) |

Typical flow: `find_station("Aachen Hbf")` → EVA number → `get_departures(eva_no)`.

### Definitions

- **EVA number** — the unique numeric ID for a station in DB's systems (e.g. `8000001` = Aachen Hbf). Station names change and duplicate; EVA numbers don't, so every endpoint below keys off of it.
- **`plan`** — the static, pre-planned timetable for one hour at a station. Never contains delays, only what *should* happen.
- **`fchg`** ("full changes") — every known real-time change (delay, platform swap, cancellation, added trip) for the current operating day. Updated every 30s.
- **`rchg`** ("recent changes") — a small subset of `fchg`: only changes from the last 2 minutes. Cheaper to poll frequently once you've already loaded `fchg` once.
- **DS100** — DB's short alphabetic code for a station (e.g. `KA` for Aachen Hbf), used internally alongside the EVA number.

## Example

Prompt:

```
When's the next train from Aachen Hbf?
```

The agent calls `find_station("Aachen Hbf")`, then `get_departures(eva_no="8000001")`, and answers from the result:

```json
{
  "id": "-5414170453134686351-2607131018-1",
  "train": "RE 92111",
  "line": "RE9",
  "departure": {
    "planned_time": "2026-07-13T10:18",
    "changed_time": "2026-07-13T10:20",
    "delay_minutes": 2,
    "platform": "3",
    "destination": "Düren"
  }
}
```

> RE9 to Düren, platform 3, 10:18 → running 2 min late, now 10:20.

### Example: historical delay pattern

Prompt:

```
How punctual has RE9 been today at Stolberg(Rheinl)Hbf?
```

The agent calls `find_station("Stolberg(Rheinl)Hbf")`, then `get_live_changes(eva_no="8000348", limit=100)`, filters the stops to `line == "RE9"`, and reasons over the `delay_minutes` across the day:

```json
[
  { "train": "RE 92111", "delay_minutes": 2 },
  { "train": "RE 92106", "delay_minutes": 1 },
  { "train": "RE 92118", "delay_minutes": 1 },
  { "train": "RE 92123", "delay_minutes": 0 },
  { "train": "RE 92125", "delay_minutes": 0 }
]
```

> RE9 has been very reliable today: 0–2 min delay across 5 trips, no cancellations. `get_live_changes` covers the whole operating day in one call, so this needs no extra polling — just one fetch per station.

## Setup

Requirements: Python ≥ 3.10, [uv](https://docs.astral.sh/uv/), free DB API credentials.

**1. Get credentials** — register at the [DB API Marketplace](https://developers.deutschebahn.com), create an application, and subscribe it to the **Timetables** API. This gives you a Client ID and an API key.

**2. Clone and configure:**

```bash
git clone https://github.com/eric134422/db-fahrplan-mcp.git
cd db-fahrplan-mcp
uv sync
cp .env.example .env   # then paste your credentials into .env
```

**3. Register with your MCP client** — e.g. Claude Code (`.mcp.json`):

```json
{
  "mcpServers": {
    "db-fahrplan": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/db-fahrplan-mcp", "run", "server.py"]
    }
  }
}
```

MCP servers are only picked up on startup, so **restart your CLI tool** (e.g. `claude`) after editing the config — a running session won't see the new server until it's relaunched.
## Architecture

```
server.py   MCP layer: FastMCP instance + the four @mcp.tool()s (stdio transport)
api.py      HTTP layer: httpx client, auth headers, error mapping
parser.py   Translation layer: DB's XML → compact JSON dicts
```

The layers are deliberately independent: `api.py` knows nothing about MCP, `parser.py` knows nothing about HTTP. Swap or test each in isolation.

### Why a parsing layer?

The Timetables API returns XML with single-letter attributes (`pt` = planned time, `ct` = changed time, `pp`/`cp` = planned/changed platform, `ppth` = route). Passing that to an LLM raw wastes context and invites misreading — a single `/fchg` response can exceed 800k characters for a major hub. `parser.py` maps the attributes to named JSON fields, computes `delay_minutes`, resolves origin/destination from the route path, and drops empty fields. `get_live_changes` additionally caps the stop list (`limit` parameter, default 30) and reports the total count.

The attribute semantics come from the official OpenAPI spec — download `Timetables-*.json` from the [DB API Marketplace](https://developers.deutschebahn.com/db-api-marketplace/apis/product/timetables) for the full dictionary.

## API quirks worth knowing

- **EVA numbers** are the primary key for everything (`8000001` = Aachen Hbf). German stations start with `80`.
- **Station search** is a prefix match on exact DB naming: `Stolberg(Rheinl)Hbf` works, `Stolberg Hbf` doesn't. Umlauts often fail; `*` works as a wildcard.
- **Times** in the raw API are `YYMMddHHmm` strings in German local time; the parser converts them to ISO (`2026-07-13T14:47`).
- **`/plan` slices are static** — they never contain delays. Real-time data lives exclusively in `/fchg` and `/rchg`, which is why `get_departures` fetches both and merges them server-side.
- **Fernverkehr (ICE/IC/EC/NJ) is included**, not just regional RE/RB/S — but in `/fchg`, an on-time long-distance train can show up as a bare stop (timestamps only, no `line`/`train` field), since the name is only attached to records that carry an actual delay/disruption. Use `/plan` (`get_departures`) if you need reliable train names for Fernverkehr.

## Roadmap

- [ ] Tests (pytest, mocked API responses)
- [ ] `get_train` — follow a single trip across stations
- [ ] Optional full route (`via` stations) in departure output
- [ ] MCPB packaging

Contributions welcome — the codebase is intentionally small and readable. Fragen und Issues gerne auch auf Deutsch.

## License

[MIT](LICENSE). Not affiliated with Deutsche Bahn AG. API data is subject to the [DB API terms](https://data.deutschebahn.com/nutzungsbedingungen.html).
