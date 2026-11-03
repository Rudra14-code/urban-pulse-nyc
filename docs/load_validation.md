# MySQL load validation

| Check | Result | Detail |
|---|---|---|
| row_count_matches_csv | PASS | MySQL 119,202 vs CSV 119,202 |
| ids_unique | PASS | 119,202 distinct of 119,202 |
| date_range_in_window | PASS | 2025-11-01 00:02:29 to 2026-10-31 23:53:38 |
| closed_count_matches | PASS | 113,574 closed |
| resolution_count_matches | PASS | 113,541 with resolution_hours |
| 5_random_rows_match | PASS | complaint_type, borough, created_date |