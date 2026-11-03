# Urban Pulse NYC: Citizen Complaint Intelligence and Resolution Analytics

End-to-end analytics on NYC 311 service requests: API extraction → cleaning → statistics/EDA → MySQL → 15 SQL investigations → Streamlit five-KPI dashboard.

**Tags:** Python · SQL · EDA · MySQL · Streamlit

## Dataset (this run)
| Item | Value |
|---|---|
| Source | NYC Open Data, 311 Service Requests from 2020 to Present (`erm2-nwe9`), https://data.cityofnewyork.us/resource/erm2-nwe9.json |
| Extracted | 2026-11-03 (UTC time stamp in `data/raw/extraction_metadata.json`) |
| Window | 2025-11-01 to 2026-11-01 (end excluded), 12 full months |
| Sampling | Systematic ~3%: requests whose `unique_key` ends in 07, 37 or 67 |
| Rows | 119,202 raw = 119,202 clean = 119,202 in MySQL |
| Fields | 25 source fields + 9 quality flags + 9 derived fields |

**Why a systematic sample and not "the latest 100k"?** NYC gets ~320k requests a month, so the latest 100k would cover only ~12 days, most still open. Taking every request whose ID ends in 07/37/67 spreads the sample evenly over all 12 months, every weekday and every hour, so trends and durations are not distorted.

## Folder structure
```
urban-pulse-nyc/
├── src/
│   ├── config.py          settings; reads MySQL credentials from .env
│   ├── extract.py         Step 1: API → data/raw (paging, retries, metadata)
│   ├── clean.py           Step 2: cleaning, flags, derived fields, log + data dictionary
│   ├── load_mysql.py      Step 3: staging table → validation → publish
│   ├── queries.py         runs the named SQL in sql/analyst_queries.sql (with safe filters)
│   ├── task_notes.py      question / pattern / interpretation for each investigation
│   ├── run_pipeline.py    runs steps 1-3 in order
│   └── setup_env.py       one-time: asks MySQL password, tests it, writes .env
├── sql/
│   ├── schema.sql         database + table definition
│   └── analyst_queries.sql  the 15 investigations + KPI query
├── notebooks/UrbanPulse_EDA_and_Analysis.ipynb   statistics + all 15 tasks with charts
├── app/streamlit_app.py   dashboard
├── data/raw/              untouched API extract + extraction metadata + run log
├── data/clean/            analysis-ready CSV (full CSVs are ~80 MB each, so not on GitHub; run_pipeline.py recreates them)
├── data/sample/           1,000-row samples of the raw and clean files (on GitHub)
├── docs/                  data dictionary, cleaning log, load validation, findings report
└── reports/figures/       PNG charts from the notebook
```

## How to run
Needs Python 3.11+ and MySQL 8 running locally.
```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env          # then put your MySQL password in .env
                                # (or run: .venv\Scripts\python src\setup_env.py)
cd src
..\.venv\Scripts\python run_pipeline.py     # extract (~12 min) -> clean -> load
cd ..
.venv\Scripts\python -m jupyter lab notebooks\UrbanPulse_EDA_and_Analysis.ipynb
.venv\Scripts\streamlit run app\streamlit_app.py
```
The SQL in `sql/analyst_queries.sql` can also be pasted straight into MySQL Workbench.

## Security
* No passwords in code. `config.py` reads `MYSQL_*` environment variables (`.env` is git-ignored; `.env.example` shows the format).
* Dashboard filters are passed as query **parameters** (`%s`), never pasted into SQL text, so a user cannot inject SQL.

## Dashboard (five KPIs)
| KPI | Definition | Full extract |
|---|---|---|
| Total requests | distinct `unique_key` in filter | 119,202 |
| Recorded closure | share of rows with a recorded closed date | 95.3% |
| Open requests | rows with no closed date | 5,628 |
| Median resolution | median of valid `resolution_hours` | 7.4 h |
| Over 72 hours | share of valid durations > 72 h (project cut-off, not an official standard) | 26.0% |

Pages: Dashboard · Analyst tasks (all 15, with SQL, chart, table, notes) · Data quality · Record preview (download) · About and limitations. Filters: date range, borough, complaint type.

## Key documents
* `docs/findings_report.md`: findings, limitations, operational implications
* `docs/data_dictionary.md` / `.csv`: every field: meaning, type, missingness, transformation, use
* `docs/cleaning_log.md`: every cleaning step and rows affected
* `docs/load_validation.md`: MySQL load checks (all PASS)
