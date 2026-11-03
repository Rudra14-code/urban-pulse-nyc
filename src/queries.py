"""Reads sql/analyst_queries.sql and runs the named queries.

The same SQL is used in MySQL Workbench, the report and the Streamlit app.
`filtered=True` swaps the first line (the `base` CTE) for a version with
parameterised filters, so user choices never get pasted into SQL text.
"""
import re

import pandas as pd
import pymysql

import config as C

BASE_LINE = "WITH base AS (SELECT * FROM service_requests)"


def load_queries() -> dict:
    text = (C.PROJECT_ROOT / "sql" / "analyst_queries.sql").read_text(encoding="utf-8")
    out = {}
    for block in re.split(r"(?m)^-- name: ", text)[1:]:
        name, rest = block.split("\n", 1)
        title = re.search(r"(?m)^-- title: (.*)$", rest).group(1).strip()
        sql = "\n".join(l for l in rest.splitlines() if not l.startswith("--")).strip().rstrip(";")
        out[name.strip()] = {"title": title, "sql": sql}
    return out


def build_base(start=None, end=None, boroughs=None, complaint_types=None):
    """Return (base_cte_sql, params) for the chosen filters."""
    where, params = [], []
    if start:
        where.append("created_date >= %s"); params.append(str(start))
    if end:
        where.append("created_date < %s"); params.append(str(end))
    if boroughs:
        where.append(f"borough IN ({','.join(['%s'] * len(boroughs))})"); params += list(boroughs)
    if complaint_types:
        where.append(f"complaint_type IN ({','.join(['%s'] * len(complaint_types))})")
        params += list(complaint_types)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    return f"WITH base AS (SELECT * FROM service_requests{clause})", params


def connect():
    return pymysql.connect(host=C.MYSQL_HOST, port=C.MYSQL_PORT, user=C.MYSQL_USER,
                           password=C.MYSQL_PASSWORD, database=C.MYSQL_DB, charset="utf8mb4",
                           connect_timeout=5)


def run(name: str, con=None, **filters) -> pd.DataFrame:
    q = load_queries()[name]
    base, params = build_base(**filters)
    sql = q["sql"].replace(BASE_LINE, base, 1)
    own = con is None
    con = con or connect()
    try:
        with con.cursor() as cur:
            cur.execute(sql, params or None)
            cols = [d[0] for d in cur.description]
            df = pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        if own:
            con.close()
    # MySQL DECIMAL -> float for charts
    for c in df.columns:
        if df[c].dtype == object and df[c].map(lambda v: v.__class__.__name__ == "Decimal").any():
            df[c] = df[c].astype(float)
    return df
