# Cleaning and validation log

Generated: 2026-11-03 13:10

- Source: https://data.cityofnewyork.us/resource/erm2-nwe9.json
- Extracted (UTC): 2026-11-03T07:35:43+00:00
- Window: 2025-11-01 to 2026-11-01 (end excluded)
- Sampling: systematic: unique_key ending in ['07', '37', '67'] (~3%)
- Raw rows: 119,202; clean rows: 119,202

Resolution-time IQR fences: Q1 = 1.17 h, Q3 = 76.26 h, IQR = 75.09 h, lower fence = -111.47 h, upper fence = 188.90 h

| Step | Detail | Rows affected |
|---|---|---|
| load | raw rows read | 119,202 |
| text | descriptor: whitespace trimmed | 18 |
| text | resolution_description: whitespace trimmed | 17,593 |
| text | incident_address: whitespace trimmed | 11,073 |
| text | street_name: whitespace trimmed | 11,073 |
| labels | complaint_type: 2 case-only variants merged | 190 |
| labels | descriptor: 3 case-only variants merged | 10 |
| labels | location_type: 1 case-only variants merged | 437 |
| labels | city: 2 case-only variants merged | 2 |
| duplicates | duplicate unique_key rows removed | 0 |
| duplicates | rows without unique_key removed | 0 |
| flags | flag_closed_before_created | 33 |
| flags | flag_zero_duration | 1,927 |
| flags | flag_future_date | 0 |
| flags | flag_status_closed_no_date | 0 |
| flags | flag_date_but_not_closed | 617 |
| flags | flag_midnight_created | 112 |
| flags | flag_missing_coords | 2,466 |
| flags | flag_coords_outside_nyc | 0 |
| flags | flag_unspecified_borough | 117 |
| derived | valid resolution_hours computed | 113,541 |
| derived | closed rows excluded from resolution_hours (invalid dates) | 33 |
| derived | IQR outliers (Q1=1.17h, Q3=76.26h, upper fence=188.90h) | 17,332 |
| save | clean rows written | 119,202 |

Rows are never deleted for being unusual. They are flagged (`flag_*` columns) so analysts can decide per question.