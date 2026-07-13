# Agent guide: presenting DB Fahrplan data

How to display results from this MCP server's tools to the user. This is about output formatting only — tool usage is documented in README.md.

## Departure / delay lists → always a table

When showing more than one train, use a Markdown table with these columns:

| Planned | Train | Result |
|---|---|---|
| 17:21 | RE4 (NX 26429) | **+27 min** |

- **Planned**: planned local time, `HH:MM`. Add the date once above the table, not per row.
- **Train**: line **and** train label, formatted `LINE (TRAIN)`, e.g. `RE4 (NX 26419)`. The line (RE4, RB33, S41 …) is what users know — never drop it, even if every row has the same line. If there is no `line` field (e.g. ICE/IC), use the train label alone: `ICE 14`.
- **Result**: the real-time outcome, one of:
  - `on time` — delay_minutes is 0
  - `+X min` — positive delay; **bold** at 15 min or more
  - `**cancelled**` — always bold; if a delay was known before cancellation, append `(+X before that)`
  - `replacement bus` — when the train runs as `Bus NNNN`; note a shortened route if the destination differs from the original
  - `no record` — no change data available; note the ambiguity: "on time or record aged out"

## Single-train answers

Prose, no table. Still use the full designation: "RE4 (NX 26425), planned 15:21, was cancelled."

## General rules

- Times in German local time, `HH:MM`, no seconds.
- Platform changes matter: mention `platform → changed_platform` when present.
- Sort rows by planned time, ascending.
- Don't show raw field names (`delay_minutes`, `eva`) to the user; translate them.
- EVA numbers only on request — users think in station names.
