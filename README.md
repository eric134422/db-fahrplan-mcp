# db-fahrplan-mcp

An (unofficial) MCP server for the [Deutsche Bahn Timetables API](https://developers.deutschebahn.com/db-api-marketplace/apis/product/timetables) — station search, planned departures, and real-time changes (delays, platform changes, cancellations) as tools for Claude and other MCP clients.

Written in Python with [FastMCP](https://github.com/modelcontextprotocol/python-sdk). The API's XML responses are parsed into compact JSON server-side, so tool outputs stay small and readable for the model.

## Tools

| Tool | API endpoint | Description |
|---|---|---|
| `find_station` | `/station/{pattern}` | Search stations by name, EVA number, or DS100 code |
| `get_departures` | `/plan/{eva}/{date}/{hour}` | Planned timetable for one hour slice (defaults to now) |
| `get_live_changes` | `/fchg/{eva}` | All known real-time changes for the current day |
| `get_recent_changes` | `/rchg/{eva}` | Only changes from the last 2 minutes (cheap polling) |

Typical flow: `find_station("Aachen Hbf")` → EVA number → `get_departures(eva_no)` + `get_live_changes(eva_no)`.

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

Or test interactively with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uv run server.py
```

## Architecture

```
server.py   MCP layer: FastMCP instance + the four @mcp.tool()s (stdio transport)
api.py      HTTP layer: httpx client, auth headers, error mapping
parser.py   Translation layer: DB's XML → compact JSON dicts
```

The layers are deliberately independent: `api.py` knows nothing about MCP, `parser.py` knows nothing about HTTP. Swap or test each in isolation.

### Why a parsing layer?

The Timetables API returns XML with single-letter attributes (`pt` = planned time, `ct` = changed time, `pp`/`cp` = planned/changed platform, `ppth` = route). Passing that to an LLM raw wastes context and invites misreading — a single `/fchg` response can exceed 50k characters. `parser.py` maps the attributes to named JSON fields, computes `delay_minutes`, resolves origin/destination from the route path, and drops empty fields. `get_live_changes` additionally caps the stop list (`limit` parameter, default 30) and reports the total count.

The attribute semantics come from the official OpenAPI spec — download `Timetables-*.json` from the [DB API Marketplace](https://developers.deutschebahn.com/db-api-marketplace/apis/product/timetables) for the full dictionary.

## API quirks worth knowing

- **EVA numbers** are the primary key for everything (`8000001` = Aachen Hbf). German stations start with `80`.
- **Station search** is a prefix match on exact DB naming: `Stolberg(Rheinl)Hbf` works, `Stolberg Hbf` doesn't. Umlauts often fail; `*` works as a wildcard.
- **Times** in the raw API are `YYMMddHHmm` strings in German local time; the parser converts them to ISO (`2026-07-13T14:47`).
- **`/plan` slices are static** — they never contain delays. Real-time data lives exclusively in `/fchg` and `/rchg`.

## Roadmap

- [ ] Tests (pytest, mocked API responses)
- [ ] `get_train` — follow a single trip across stations
- [ ] Optional full route (`via` stations) in departure output
- [ ] MCPB packaging

Contributions welcome — the codebase is intentionally small and readable. Fragen und Issues gerne auch auf Deutsch.

## License

[MIT](LICENSE). Not affiliated with Deutsche Bahn AG. API data is subject to the [DB API terms](https://data.deutschebahn.com/nutzungsbedingungen.html).
