# Urban Pulse NYC: Findings report

**Data:** 119,202 NYC 311 requests (systematic ~3% sample), created 1 Nov 2025 to 31 Oct 2026, extracted 3 Nov 2026.
All numbers below come from `sql/analyst_queries.sql` run on `urban_pulse_db.service_requests`.

## Headline
* Most requests close fast; a minority take weeks. **Median 7.4 h vs mean 154.6 h** (skewness 6.2). 43% close within 4 hours; 26% take over 72 hours; 5.9% take over 30 days.
* **Two kinds of work hide inside one average.** Durations form two humps: around 1 hour (NYPD parking/noise calls, median 1.4 h) and around 2-4 days (inspections: HPD housing median 97 h, DOHMH 222 h).
* **Housing is both common and slow.** Among the top-20 categories by volume, DOOR/WINDOW (313 h), UNSANITARY CONDITION (270 h), WATER LEAK (262 h), PLUMBING (218 h) and PAINT/PLASTER (195 h) have medians 26-42× the overall median. HEAT/HOT WATER (3rd largest category) has a 43 h median.

## The 15 investigations
| # | Question | Finding |
|---|---|---|
| 1 | Total volume | 119,202 distinct requests, no duplicate IDs, 12 months |
| 2 | Top categories | Illegal Parking 15.6%, Noise - Residential 10.6%, HEAT/HOT WATER 8.9% (top 3 = 35%) |
| 3 | Agency workload | NYPD 43.6%, HPD 22.9%; top 5 agencies = 88% |
| 4 | Borough volume | Brooklyn 31%, Queens 24%, Bronx 21%, Manhattan 19%, Staten Island 4% |
| 5 | Monthly trend | Steady ~9.1k-10.4k per month; closed share falls from 98.6% to 83.7% in the newest month (timing effect) |
| 6 | Weekday × hour | Weekday peak 09:00-11:00 (Tue 10:00 busiest); weekend nights (Sat 22:00, Sun 00:00) spike with noise |
| 7 | Statuses | 94.8% CLOSED; 617 non-closed rows still carry a closed date |
| 8 | Duration stats | n 113,541; median 7.4 h; Q1 1.2 h; Q3 76.3 h; max 8,538 h; SD 474 h |
| 9 | Slowest categories | Taxi Complaint ~3,745 h; For Hire Vehicle ~2,019 h; food/vape inspections ≈ 1,440 h (= exactly 60 days, likely an administrative closure rule) |
| 10 | Slowest agencies | OOS 1,072 h, DCWP 597 h, TLC 426 h ... NYPD 1.4 h |
| 11 | IQR outliers | Upper fence 189 h; 15% of durations above it, mostly HPD housing categories, so long is normal there |
| 12 | Skewness/distribution | Skewness 6.23; strongly right-skewed |
| 13 | Geography | 97.9% of rows have usable coordinates. Top ~1 km cell (Bronx) is mostly **one address**: 655 East 230 Street, 1,421 Noise - Residential requests. Other hotspots: HEAT/HOT WATER in the Bronx / upper Manhattan |
| 14 | Closure rate by agency | NYPD 99.9%, DOB 100%; DPR 63.8%, TLC 40.2%; EDC 0% (all 329 are Noise - Helicopter, left IN PROGRESS) |
| 15 | High volume + slow | DOOR/WINDOW, UNSANITARY CONDITION, WATER LEAK, PLUMBING, PAINT/PLASTER, Noise, Snow or Ice, HEAT/HOT WATER, Street Condition, Dirty Condition |

## Data quality summary
No duplicate IDs; no future dates; 33 closed-before-created rows (excluded from durations only); 1,927 zero-second closures (kept, flagged); 2,466 rows (2.1%) without coordinates; 117 rows with unspecified borough; 112 midnight-stamped rows. Full list: `cleaning_log.md`.

## Possible operational implications (cautious)
1. **Staffing:** intake demand peaks on weekday mornings; weekend late nights need noise-response cover.
2. **Housing backlog:** HPD categories combine high volume with long durations; they are the clearest target for process review.
3. **Repeat callers:** single addresses can create hotspots; de-duplicating repeat reports would make maps and workload figures more honest.
4. **Closure rules:** the 60-day spike and EDC's 0% closure suggest recording rules, not effort; check definitions before comparing agencies.
5. **Channels:** mobile/online requests have lower median durations (2.1 h / 5.6 h) than phone (47.6 h), but this mostly reflects which complaint types use which channel.

## Limitations
* 311 counts reported requests, not how common problems really are; reporting habits differ by area.
* ~3% sample on one extraction date; the live dataset changes daily.
* Recent months look less closed because they had less time to close.
* Agency/category comparisons reflect different complexity and definitions, not efficiency.
* Recorded closure ≠ problem fixed or citizen satisfied. The 72-hour cut-off is a project choice.
* SQL medians use the nearest-rank method; pandas uses interpolation, so they can differ slightly.
