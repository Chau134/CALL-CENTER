# Raw Data Baseline — Before ETL

Generated at UTC: `2026-11-04T12:33:08.630251+00:00`

This snapshot is the reconciliation evidence for the unmodified Technion source. It contains no customer IDs or agent names.

## Dataset totals

- Monthly files: **12**
- Total raw rows: **444,448**
- Structurally well-formed rows: **444,436**
- Malformed delimiter rows: **12**
- Date coverage: **1999-01-01 to 1999-12-31**
- Distinct agent labels, names suppressed: **52**

## Raw distributions

- Outcomes: `{"0:00:00": 12, "AGENT": 353143, "HANG": 87694, "PHANTOM": 3599}`
- Service types: `{"990703": 1, "990706": 1, "990717": 1, "990719": 1, "990729": 1, "990802": 1, "990809": 1, "990812": 1, "990830": 1, "990914": 1, "991026": 2, "AA": 5, "IN": 20727, "NE": 39342, "NW": 67727, "PE": 1824, "PS": 302521, "TT": 12290}`
- Priorities: `{"0": 235156, "0       IN": 5, "0       NW": 1, "0       PS": 1, "0       TT": 5, "1": 71827, "2": 137453}`

## Quality evidence

- Unexpected outcomes: `{"0:00:00": 12}`
- Unexpected service types: `{"990703": 1, "990706": 1, "990717": 1, "990719": 1, "990729": 1, "990802": 1, "990809": 1, "990812": 1, "990830": 1, "990914": 1, "991026": 2, "AA": 5}`
- Unexpected priorities: `{"0       IN": 5, "0       NW": 1, "0       PS": 1, "0       TT": 5}`
- Invalid durations: `{"q_time": 12, "ser_time": 12, "vru_time": 12}`
- Negative durations: `{"q_time": 0, "ser_time": 0, "vru_time": 350}`
- Duplicate source-key rows within month: **0**

## Monthly files

| File | Rows | Bytes | Malformed | SHA-256 |
|---|---:|---:|---:|---|
| `April1999.txt` | 32,036 | 3,364,875 | 0 | `cf51f7f2c8d19ae68181d0b51f3e41ce58a5d5d97c4d81dada728f061fd6211d` |
| `August1999.txt` | 42,078 | 4,335,396 | 4 | `2a61cf61d52cc62d18d0fe96f89aae8b5378d5b345775ecfcbe704bf30d9af60` |
| `December1999.txt` | 43,065 | 4,462,235 | 0 | `1c723ffc05d1567d59025b1b68079739bc4c339f80aafba4398ee80f639a3209` |
| `February1999.txt` | 33,344 | 3,453,308 | 0 | `4004237dcb32355816e9bf98b9a61401ec4ded56c5c66c4a51d3e78f9802cf46` |
| `January1999.txt` | 31,599 | 3,273,725 | 0 | `0274cfb02703a5ffadc7d381064cb177ac0b4be2fe6ce439283e80d95de9103f` |
| `July1999.txt` | 39,022 | 4,052,059 | 5 | `80012ee43912072e26c3fc00369a925e75102b61776e25130bfac8750addd9b0` |
| `June1999.txt` | 37,935 | 3,950,119 | 0 | `29c6c4f2202c2a1771ed0c490ba708cf3fc798afe664fd3058d78df76adec495` |
| `March1999.txt` | 38,801 | 4,084,663 | 0 | `3d95552ceff76390d8bd78aa7d166fb2fd077cb74a8b08f2000ab1334ce9a118` |
| `May1999.txt` | 39,553 | 4,146,417 | 0 | `9efbd488959bbd8cf3489140fa599784364d41f334bc9a1db29e95b611308325` |
| `November1999.txt` | 41,019 | 4,281,181 | 0 | `20df9fc55b894fd8695540e5060e0ed74dc0c6c7ad596d4a97113932e2483511` |
| `October1999.txt` | 34,625 | 3,495,145 | 2 | `078b3faccfbc86b8ca97d8c0ad2750119e6a36fd5184d058330e16f698a81932` |
| `September1999.txt` | 31,371 | 3,190,748 | 1 | `a6d8a914d232b02b171279033ec8c87c3f607ed218a86c36c06847769a15f00d` |

## Reconciliation identity

After ETL, the following identity must be explained exactly:

```text
total_raw_rows
= clean_rows
+ excluded_rows
+ quarantine_rows
```

No row may disappear without an exclusion or quarantine reason.
