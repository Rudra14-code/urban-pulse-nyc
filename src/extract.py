"""Step 1 - Extract NYC 311 service requests from the NYC Open Data API.

What it does, in plain words:
  * asks the API for one month at a time (12 months)
  * inside each month, keeps only requests whose ID ends in 07, 37 or 67
    (a systematic ~3% sample spread evenly across every day and hour)
  * pages through results 5,000 rows at a time
  * retries if the API is temporarily busy (waits longer each time)
  * saves the untouched raw data + a metadata file describing the run
"""
import json
import time
from datetime import datetime, timezone

import pandas as pd
import requests

import config as C


def month_windows(start: str, end: str):
    """Yield (month_start, next_month_start) pairs between start and end."""
    months = pd.date_range(start, end, freq="MS")
    for a, b in zip(months[:-1], months[1:]):
        yield a.strftime("%Y-%m-%dT00:00:00"), b.strftime("%Y-%m-%dT00:00:00")


class TemporaryAPIError(Exception):
    """API is busy or briefly down; worth trying again."""


def get_page(session: requests.Session, params: dict) -> list:
    """One API call with retry + exponential back-off for temporary errors."""
    for attempt in range(1, C.MAX_RETRIES + 1):
        try:
            r = session.get(C.API_URL, params=params, timeout=C.TIMEOUT_S)
            if r.status_code in (429, 500, 502, 503, 504):
                raise TemporaryAPIError(f"HTTP {r.status_code}")
            r.raise_for_status()  # other errors (e.g. 400 bad query) stop the run
            return r.json()
        except (requests.Timeout, requests.ConnectionError, TemporaryAPIError) as e:
            if attempt == C.MAX_RETRIES:
                raise
            wait = 5 * 2 ** (attempt - 1)   # 5s, 10s, 20s, 40s
            print(f"    attempt {attempt} failed ({e}); retrying in {wait}s")
            time.sleep(wait)


def extract() -> pd.DataFrame:
    session = requests.Session()
    if C.APP_TOKEN:
        session.headers["X-App-Token"] = C.APP_TOKEN

    rows, log = [], []
    started = datetime.now(timezone.utc)
    for m_start, m_end in month_windows(C.WINDOW_START, C.WINDOW_END):
        for suffix in C.KEY_SUFFIXES:
            where = (f"created_date >= '{m_start}' AND created_date < '{m_end}' "
                     f"AND unique_key like '%{suffix}'")
            offset, got = 0, 0
            while True:
                page = get_page(session, {
                    "$select": ",".join(C.FIELDS),
                    "$where": where,
                    "$order": "unique_key",
                    "$limit": C.PAGE_SIZE,
                    "$offset": offset,
                })
                rows.extend(page)
                got += len(page)
                if len(page) < C.PAGE_SIZE:
                    break
                offset += C.PAGE_SIZE
            log.append({"month": m_start[:7], "suffix": suffix, "rows": got})
            print(f"{m_start[:7]} ending {suffix}: {got:,} rows (total {len(rows):,})")

    df = pd.DataFrame(rows).reindex(columns=C.FIELDS)
    df.to_csv(C.RAW_CSV, index=False, encoding="utf-8")

    meta = {
        "source": C.API_URL,
        "dataset": "311 Service Requests from 2020 to Present (erm2-nwe9)",
        "extracted_at_utc": started.isoformat(timespec="seconds"),
        "window_start": C.WINDOW_START,
        "window_end_exclusive": C.WINDOW_END,
        "sampling": f"systematic: unique_key ending in {C.KEY_SUFFIXES} (~{len(C.KEY_SUFFIXES)}%)",
        "fields": C.FIELDS,
        "page_size": C.PAGE_SIZE,
        "rows_extracted": len(df),
        "per_month_suffix": log,
        "limitations": [
            "Data changes daily; re-running gives slightly different results.",
            "Recent months have more open requests because they had less time to close.",
            "Sample is ~3% of requests, not the full population.",
        ],
    }
    C.RAW_META.write_text(json.dumps(meta, indent=2))
    print(f"\nSaved {len(df):,} raw rows -> {C.RAW_CSV}")
    return df


if __name__ == "__main__":
    extract()
