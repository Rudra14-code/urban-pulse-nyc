"""Step 2 - Clean the raw extract and add derived fields.

Rules we follow (from the project brief):
  * keep the raw file untouched; write a separate cleaned file
  * fix only what is clearly safe (spaces, letter-case duplicates, data types)
  * keep meaningful blanks as blanks (a blank closed_date means "not closed")
  * FLAG odd values instead of silently fixing or deleting them
  * write a cleaning log so every change can be traced
"""
import json
from datetime import datetime

import numpy as np
import pandas as pd

import config as C

DATE_COLS = ["created_date", "closed_date", "due_date", "resolution_action_updated_date"]
TEXT_COLS = [c for c in C.FIELDS if c not in DATE_COLS + ["latitude", "longitude"]]
# Rough NYC bounding box; points outside it are flagged, not deleted
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 40.47, 40.93, -74.27, -73.68

log = []  # (step, detail, rows affected)


def note(step, detail, n):
    log.append({"step": step, "detail": detail, "rows_affected": int(n)})
    print(f"[{step}] {detail}: {int(n):,}")


def clean() -> pd.DataFrame:
    meta = json.loads(C.RAW_META.read_text())
    extracted_at = pd.Timestamp(meta["extracted_at_utc"]).tz_localize(None)

    df = pd.read_csv(C.RAW_CSV, dtype=str, keep_default_na=False)
    note("load", "raw rows read", len(df))

    # 1. Text tidy-up: trim spaces, collapse double spaces, blank -> missing
    for c in TEXT_COLS:
        s = df[c].str.strip().str.replace(r"\s+", " ", regex=True)
        changed = (s != df[c]).sum()
        if changed:
            note("text", f"{c}: whitespace trimmed", changed)
        df[c] = s.replace({"": np.nan, "N/A": np.nan, "NA": np.nan})

    # 2. Category labels: merge values that differ only by letter case
    for c in ["complaint_type", "descriptor", "location_type", "city"]:
        s = df[c].dropna()
        groups = s.groupby(s.str.upper())
        mapping = {}
        for _, g in groups:
            variants = g.value_counts()
            if len(variants) > 1:  # e.g. 'Noise - Street/Sidewalk' vs 'NOISE - STREET/SIDEWALK'
                keep = variants.index[0]  # most common spelling wins
                for v in variants.index[1:]:
                    mapping[v] = keep
        if mapping:
            n = df[c].isin(mapping.keys()).sum()
            df[c] = df[c].replace(mapping)
            note("labels", f"{c}: {len(mapping)} case-only variants merged", n)
    for c in ["borough", "park_borough", "status", "agency", "address_type", "open_data_channel_type"]:
        df[c] = df[c].str.upper()
    df["city"] = df["city"].str.upper()

    # 3. Dates: text -> real timestamps (bad text becomes missing and is counted)
    for c in DATE_COLS:
        df[c] = df[c].str.strip().replace({"": np.nan})   # blank = genuinely not recorded
        parsed = pd.to_datetime(df[c], errors="coerce", format="ISO8601")
        bad = df[c].notna() & parsed.isna()
        if bad.any():
            note("dates", f"{c}: unparseable values set to missing", bad.sum())
        df[c] = parsed

    # 4. Numbers: coordinates -> floats
    for c in ["latitude", "longitude"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["unique_key"] = pd.to_numeric(df["unique_key"], errors="coerce").astype("Int64")

    # 5. Duplicate request IDs (should be none; keep first copy if any)
    dup = df["unique_key"].duplicated(keep="first")
    note("duplicates", "duplicate unique_key rows removed", dup.sum())
    df = df[~dup].copy()
    miss_key = df["unique_key"].isna()
    note("duplicates", "rows without unique_key removed", miss_key.sum())
    df = df[~miss_key].copy()

    # 6. Data-quality flags (1 = something to look at)
    created, closed = df["created_date"], df["closed_date"]
    df["flag_closed_before_created"] = (closed < created).astype(int)
    df["flag_zero_duration"] = (closed == created).astype(int)
    df["flag_future_date"] = ((created > extracted_at) | (closed > extracted_at)).astype(int)
    df["flag_status_closed_no_date"] = ((df["status"] == "CLOSED") & closed.isna()).astype(int)
    df["flag_date_but_not_closed"] = ((df["status"] != "CLOSED") & closed.notna()).astype(int)
    df["flag_midnight_created"] = (
        (created.dt.hour == 0) & (created.dt.minute == 0) & (created.dt.second == 0)).astype(int)
    has_xy = df["latitude"].notna() & df["longitude"].notna()
    df["flag_missing_coords"] = (~has_xy).astype(int)
    df["flag_coords_outside_nyc"] = (has_xy & ~(
        df["latitude"].between(LAT_MIN, LAT_MAX) & df["longitude"].between(LON_MIN, LON_MAX))).astype(int)
    df["flag_unspecified_borough"] = (df["borough"].isna() | (df["borough"] == "UNSPECIFIED")).astype(int)
    for f in [c for c in df.columns if c.startswith("flag_")]:
        note("flags", f, df[f].sum())

    # 7. Derived fields
    df["is_closed"] = closed.notna().astype(int)  # closure = a recorded closed date
    valid = (df["is_closed"] == 1) & (df["flag_closed_before_created"] == 0) & (df["flag_future_date"] == 0)
    df["resolution_hours"] = np.where(valid, (closed - created).dt.total_seconds() / 3600, np.nan)
    df["resolution_hours"] = df["resolution_hours"].round(3)
    note("derived", "valid resolution_hours computed", df["resolution_hours"].notna().sum())
    note("derived", "closed rows excluded from resolution_hours (invalid dates)",
         ((df["is_closed"] == 1) & ~valid).sum())

    df["created_year"] = created.dt.year
    df["created_month"] = created.dt.strftime("%Y-%m")
    df["created_weekday"] = created.dt.day_name()
    df["created_weekday_num"] = created.dt.day_of_week  # Monday = 0
    df["created_hour"] = created.dt.hour

    r = df["resolution_hours"]
    q1, q3 = r.quantile([0.25, 0.75])
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    df["res_outlier_iqr"] = np.where(r.notna(), ((r < lo) | (r > hi)).astype(float), np.nan)
    df["over_72h"] = np.where(r.notna(), (r > C.SLA_HOURS).astype(float), np.nan)
    note("derived", f"IQR outliers (Q1={q1:.2f}h, Q3={q3:.2f}h, upper fence={hi:.2f}h)",
         (df["res_outlier_iqr"] == 1).sum())

    df.to_csv(C.CLEAN_CSV, index=False, date_format="%Y-%m-%d %H:%M:%S")
    note("save", "clean rows written", len(df))

    write_log(meta, df, (q1, q3, iqr, lo, hi))
    write_dictionary(df)
    return df


def write_log(meta, df, fences):
    q1, q3, iqr, lo, hi = fences
    lines = ["# Cleaning and validation log", "",
             f"Generated: {datetime.now():%Y-%m-%d %H:%M}", "",
             f"- Source: {meta['source']}",
             f"- Extracted (UTC): {meta['extracted_at_utc']}",
             f"- Window: {meta['window_start']} to {meta['window_end_exclusive']} (end excluded)",
             f"- Sampling: {meta['sampling']}",
             f"- Raw rows: {meta['rows_extracted']:,}; clean rows: {len(df):,}", "",
             f"Resolution-time IQR fences: Q1 = {q1:.2f} h, Q3 = {q3:.2f} h, IQR = {iqr:.2f} h, "
             f"lower fence = {lo:.2f} h, upper fence = {hi:.2f} h", "",
             "| Step | Detail | Rows affected |", "|---|---|---|"]
    lines += [f"| {e['step']} | {e['detail']} | {e['rows_affected']:,} |" for e in log]
    lines += ["", "Rows are never deleted for being unusual. They are flagged (`flag_*` columns) "
              "so analysts can decide per question."]
    (C.DOCS_DIR / "cleaning_log.md").write_text("\n".join(lines), encoding="utf-8")


MEANING = {
    "unique_key": "Unique ID of the 311 request",
    "created_date": "When the request was created",
    "closed_date": "When the request was closed (blank = not closed yet)",
    "due_date": "Date the agency was expected to respond by (sparsely filled)",
    "resolution_action_updated_date": "Last time the resolution was updated",
    "agency": "Short code of the agency handling the request",
    "agency_name": "Full agency name",
    "complaint_type": "Top-level complaint category",
    "descriptor": "More detailed sub-category of the complaint",
    "location_type": "Type of place (street, residential building, etc.)",
    "status": "Current recorded status (Closed, Open, In Progress...)",
    "resolution_description": "Agency's text on what was done",
    "borough": "NYC borough of the incident",
    "incident_zip": "ZIP code of the incident",
    "city": "City/neighbourhood name entered",
    "incident_address": "Street address of the incident",
    "street_name": "Street name",
    "address_type": "How the location was given (address, intersection...)",
    "community_board": "Community board area",
    "council_district": "City council district",
    "police_precinct": "Police precinct",
    "open_data_channel_type": "How the request came in (phone, online, mobile...)",
    "park_borough": "Borough per the parks field",
    "latitude": "Latitude of the incident (WGS84)",
    "longitude": "Longitude of the incident (WGS84)",
    "is_closed": "1 if a closed_date is recorded, else 0",
    "resolution_hours": "Hours from created to closed; only for valid closed rows",
    "created_year": "Year of created_date",
    "created_month": "Year-month of created_date (YYYY-MM)",
    "created_weekday": "Weekday name of created_date",
    "created_weekday_num": "Weekday number (Monday=0)",
    "created_hour": "Hour of day of created_date (0-23)",
    "res_outlier_iqr": "1 if resolution_hours is outside the 1.5xIQR fences",
    "over_72h": "1 if resolution_hours > 72 (project cut-off, not an official SLA)",
    "flag_closed_before_created": "Closed date earlier than created date (impossible)",
    "flag_zero_duration": "Closed at the exact same second it was created",
    "flag_future_date": "A date later than the extraction time",
    "flag_status_closed_no_date": "Status says CLOSED but no closed_date",
    "flag_date_but_not_closed": "Has closed_date but status is not CLOSED",
    "flag_midnight_created": "Created exactly 00:00:00 (likely date-only entry; distorts hour analysis)",
    "flag_missing_coords": "Latitude or longitude missing",
    "flag_coords_outside_nyc": "Coordinates outside the NYC bounding box",
    "flag_unspecified_borough": "Borough missing or 'UNSPECIFIED'",
}
USE = {
    "unique_key": "Counting distinct requests; primary key",
    "created_date": "Trends, filters, durations", "closed_date": "Closure and durations",
    "agency": "Workload by agency", "complaint_type": "Top categories, filters",
    "borough": "Borough comparison, filters", "status": "Status distribution",
    "latitude": "Map", "longitude": "Map", "resolution_hours": "Duration statistics, KPIs",
    "is_closed": "Closure-rate KPI", "over_72h": "Over-72h KPI",
    "created_month": "Monthly trend", "created_weekday": "Weekday x hour heatmap",
    "created_hour": "Weekday x hour heatmap", "res_outlier_iqr": "Outlier investigation",
}


def write_dictionary(df):
    rows = []
    for c in df.columns:
        source = "API" if c in C.FIELDS else "derived"
        if c in DATE_COLS:
            transform = "Parsed text to datetime; unparseable -> missing"
        elif c in ("latitude", "longitude"):
            transform = "Converted to number"
        elif source == "derived":
            transform = "Computed in clean.py"
        else:
            transform = "Trimmed spaces; blank -> missing"
        rows.append({
            "field": c, "source": source, "meaning": MEANING.get(c, ""),
            "dtype": str(df[c].dtype), "missing_count": int(df[c].isna().sum()),
            "missing_pct": round(df[c].isna().mean() * 100, 2),
            "distinct_values": int(df[c].nunique()),
            "transformation": transform, "analytical_use": USE.get(c, "Context / drill-down"),
        })
    dd = pd.DataFrame(rows)
    dd.to_csv(C.DOCS_DIR / "data_dictionary.csv", index=False)
    md = ["# Data dictionary", "", "| " + " | ".join(dd.columns) + " |",
          "|" + "---|" * len(dd.columns)]
    md += ["| " + " | ".join(str(v) for v in r) + " |" for r in dd.itertuples(index=False)]
    (C.DOCS_DIR / "data_dictionary.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    clean()
