"""Step 3 - Load the cleaned data into MySQL safely.

Plain-words version:
  1. create the database + an empty STAGING table (sql/schema.sql)
  2. insert rows in batches of 2,000 (retry a batch if MySQL hiccups)
  3. VALIDATE: row count matches the CSV, IDs unique, dates in range,
     a few random rows match the CSV exactly
  4. only if every check passes, PUBLISH: swap staging in as
     service_requests in one atomic step (the old table is kept as backup
     until the swap succeeds, then dropped)
"""
import time

import numpy as np
import pandas as pd
import pymysql

import config as C

BATCH = 2000


def connect(db=None):
    return pymysql.connect(host=C.MYSQL_HOST, port=C.MYSQL_PORT, user=C.MYSQL_USER,
                           password=C.MYSQL_PASSWORD, database=db, charset="utf8mb4",
                           autocommit=False)


def run_schema():
    sql = (C.PROJECT_ROOT / "sql" / "schema.sql").read_text()
    with connect() as con, con.cursor() as cur:
        for s in sql.split(";"):
            body = "\n".join(l for l in s.splitlines() if not l.strip().startswith("--")).strip()
            if body:
                cur.execute(body)
        con.commit()
    print("schema ready (database + empty staging table)")


def load_csv() -> pd.DataFrame:
    df = pd.read_csv(C.CLEAN_CSV, dtype={"incident_zip": str, "council_district": str})
    for c in ["created_date", "closed_date", "due_date", "resolution_action_updated_date"]:
        df[c] = pd.to_datetime(df[c])
    return df


def insert_batches(df: pd.DataFrame):
    cols = list(df.columns)
    placeholders = ",".join(["%s"] * len(cols))
    sql = (f"INSERT INTO {C.STAGING_TABLE} ({','.join(cols)}) VALUES ({placeholders})")
    # pandas NaN/NaT -> SQL NULL
    clean = df.astype(object).where(df.notna(), None)
    records = [tuple(r) for r in clean.itertuples(index=False)]
    with connect(C.MYSQL_DB) as con:
        for i in range(0, len(records), BATCH):
            chunk = records[i:i + BATCH]
            for attempt in range(1, 4):
                try:
                    with con.cursor() as cur:
                        cur.executemany(sql, chunk)   # parameterised: values never pasted into SQL text
                    con.commit()
                    break
                except pymysql.err.OperationalError as e:
                    con.rollback()
                    if attempt == 3:
                        raise
                    print(f"  batch {i} failed ({e}); retry {attempt}")
                    time.sleep(3 * attempt)
                    con.ping(reconnect=True)
            if (i // BATCH) % 10 == 0:
                print(f"  inserted {min(i + BATCH, len(records)):,} / {len(records):,}")


def validate(df: pd.DataFrame) -> dict:
    checks = {}
    with connect(C.MYSQL_DB) as con, con.cursor() as cur:
        cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT unique_key), MIN(created_date), MAX(created_date), "
                    f"SUM(is_closed), SUM(resolution_hours IS NOT NULL) FROM {C.STAGING_TABLE}")
        n, n_distinct, dmin, dmax, n_closed, n_res = cur.fetchone()
        checks["row_count_matches_csv"] = (n == len(df), f"MySQL {n:,} vs CSV {len(df):,}")
        checks["ids_unique"] = (n == n_distinct, f"{n_distinct:,} distinct of {n:,}")
        checks["date_range_in_window"] = (
            str(dmin) >= C.WINDOW_START and str(dmax) < C.WINDOW_END, f"{dmin} to {dmax}")
        checks["closed_count_matches"] = (int(n_closed) == int(df["is_closed"].sum()),
                                          f"{int(n_closed):,} closed")
        checks["resolution_count_matches"] = (int(n_res) == int(df["resolution_hours"].notna().sum()),
                                              f"{int(n_res):,} with resolution_hours")
        sample = df.sample(5, random_state=42)
        ok = True
        for _, row in sample.iterrows():
            cur.execute(f"SELECT complaint_type, borough, created_date FROM {C.STAGING_TABLE} "
                        f"WHERE unique_key = %s", (int(row["unique_key"]),))
            got = cur.fetchone()
            exp = (None if pd.isna(row["complaint_type"]) else row["complaint_type"],
                   None if pd.isna(row["borough"]) else row["borough"],
                   row["created_date"].to_pydatetime())
            ok &= got == exp
        checks["5_random_rows_match"] = (ok, "complaint_type, borough, created_date")
    for k, (passed, detail) in checks.items():
        print(f"  {'PASS' if passed else 'FAIL'}  {k}: {detail}")
    return checks


def publish():
    with connect(C.MYSQL_DB) as con, con.cursor() as cur:
        cur.execute(f"CREATE TABLE IF NOT EXISTS {C.TABLE} LIKE {C.STAGING_TABLE}")
        cur.execute(f"DROP TABLE IF EXISTS {C.TABLE}_old")
        # one atomic swap: readers never see a half-loaded table
        cur.execute(f"RENAME TABLE {C.TABLE} TO {C.TABLE}_old, {C.STAGING_TABLE} TO {C.TABLE}")
        cur.execute(f"DROP TABLE {C.TABLE}_old")
        con.commit()
    print(f"published -> {C.MYSQL_DB}.{C.TABLE}")


def main():
    df = load_csv()
    print(f"clean CSV rows: {len(df):,}")
    run_schema()
    insert_batches(df)
    print("validating staging table...")
    checks = validate(df)
    if not all(p for p, _ in checks.values()):
        raise SystemExit("Validation failed: staging NOT published. Fix and re-run.")
    publish()
    lines = ["# MySQL load validation", "", "| Check | Result | Detail |", "|---|---|---|"]
    lines += [f"| {k} | {'PASS' if p else 'FAIL'} | {d} |" for k, (p, d) in checks.items()]
    (C.DOCS_DIR / "load_validation.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
