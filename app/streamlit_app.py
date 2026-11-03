"""Urban Pulse NYC - Streamlit dashboard.

Run:  .venv\\Scripts\\streamlit run app/streamlit_app.py
Every number on screen comes from MySQL through the SQL in sql/analyst_queries.sql.
Filters are passed as query parameters, never pasted into the SQL text.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config as C            # noqa: E402
import queries as Q           # noqa: E402
from task_notes import NOTES  # noqa: E402

st.set_page_config(page_title="Urban Pulse NYC", page_icon=None, layout="wide")
SQL = Q.load_queries()


# ---------------- data access (cached, with friendly errors) ----------------
@st.cache_data(ttl=600, show_spinner=False)
def run_query(name, start, end, boroughs, ctypes):
    return Q.run(name, start=start, end=end, boroughs=list(boroughs), complaint_types=list(ctypes))


@st.cache_data(ttl=600, show_spinner=False)
def run_raw(sql, params=()):
    con = Q.connect()
    try:
        with con.cursor() as cur:
            cur.execute(sql, list(params) or None)
            return pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])
    finally:
        con.close()


def safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:  # connection or SQL problem -> readable message, app keeps running
        st.error("Could not reach the MySQL database `urban_pulse_db`.\n\n"
                 "Check that the MySQL80 service is running and that `.env` has the right password "
                 f"(see README). Technical detail: `{type(e).__name__}: {e}`")
        st.stop()


# ---------------- sidebar filters ----------------
st.sidebar.title("Urban Pulse NYC")
page = st.sidebar.radio("Page", ["Dashboard (5 KPIs)", "Analyst tasks", "Data quality",
                                 "Record preview", "About and limitations"])
st.sidebar.markdown("---")
st.sidebar.subheader("Filters")

bounds = safe(run_raw, "SELECT MIN(DATE(created_date)) AS lo, MAX(DATE(created_date)) AS hi FROM service_requests")
lo, hi = bounds.lo[0], bounds.hi[0]
picked = st.sidebar.date_input("Created between", (lo, hi), min_value=lo, max_value=hi)
start, end = (picked if isinstance(picked, (list, tuple)) and len(picked) == 2 else (lo, hi))
end_excl = end + timedelta(days=1)   # include the whole last day

all_boroughs = safe(run_raw, "SELECT DISTINCT borough FROM service_requests WHERE borough IS NOT NULL ORDER BY 1").borough.tolist()
boroughs = tuple(st.sidebar.multiselect("Borough", all_boroughs, placeholder="All boroughs"))
all_types = safe(run_raw, "SELECT complaint_type, COUNT(*) n FROM service_requests GROUP BY 1 ORDER BY n DESC").complaint_type.tolist()
ctypes = tuple(st.sidebar.multiselect("Complaint type", all_types, placeholder="All complaint types"))
st.sidebar.caption("Leave a filter empty to include everything.")

F = (str(start), str(end_excl), boroughs, ctypes)


def q(name):
    return safe(run_query, name, *F)


def filter_label():
    parts = [f"{start:%d %b %Y} to {end:%d %b %Y}"]
    parts.append(", ".join(boroughs) if boroughs else "all boroughs")
    parts.append(f"{len(ctypes)} complaint type(s)" if ctypes else "all complaint types")
    return " | ".join(parts)


kpi = q("KPI")
if int(kpi.total_requests[0] or 0) == 0 and page not in ("About and limitations",):
    st.title(page)
    st.info("No requests match these filters. Widen the date range or clear the borough / complaint-type filters.")
    st.stop()


# ---------------- charts per task ----------------
def chart(name, df):
    spec = NOTES.get(name, {}).get("chart")
    if df.empty or spec is None:
        return None
    if spec.startswith("bar_h"):
        kind, x, y = spec.split(":")
        d = df.head(15) if kind == "bar_h_top15" else df
        fig = px.bar(d, x=y, y=x, orientation="h", text=y)
        fig.update_yaxes(categoryorder="total ascending", title=None)
        return fig
    if spec.startswith("bar_v"):
        _, x, y = spec.split(":")
        return px.bar(df, x=x, y=y, text=y)
    if spec.startswith("line"):
        fig = px.line(df, x="created_month", y="requests", markers=True)
        fig.add_bar(x=df.created_month, y=df.closed_pct, name="closed %", yaxis="y2", opacity=.3)
        fig.update_layout(yaxis2=dict(overlaying="y", side="right", range=[0, 100], title="closed %"),
                          yaxis=dict(rangemode="tozero"))
        return fig
    if spec == "heatmap":
        order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        p = df.pivot_table(index="created_weekday", columns="created_hour", values="requests").reindex(order)
        return px.imshow(p, aspect="auto", color_continuous_scale="YlOrRd",
                         labels=dict(x="hour", y="", color="requests"))
    if spec == "map":
        return px.scatter_map(df, lat="lat_cell", lon="lon_cell", size="requests", color="borough",
                              hover_data=["top_complaint", "requests"], zoom=9.3, height=500)
    if spec == "scatter":
        return px.scatter(df, x="requests", y="median_h", text="complaint_type", log_x=True, log_y=True,
                          labels={"median_h": "median hours"})
    return None


# ================= PAGES =================
if page == "Dashboard (5 KPIs)":
    st.title("Urban Pulse NYC: 311 service requests")
    st.caption(filter_label())
    k = kpi.iloc[0]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total requests", f"{int(k.total_requests):,}", help="Distinct request IDs in the filtered data")
    c2.metric("Recorded closure", f"{k.closure_pct:.1f}%", help="Share of filtered rows with a recorded closed date")
    c3.metric("Open requests", f"{int(k.open_requests):,}", help="Filtered rows with no closed date")
    c4.metric("Median resolution", "n/a" if pd.isna(k.median_resolution_h) else f"{k.median_resolution_h:.1f} h",
              help="Median of valid resolution durations (closed after created)")
    c5.metric("Over 72 hours", "n/a" if pd.isna(k.over_72h_pct) else f"{k.over_72h_pct:.1f}%",
              help="Share of valid durations above 72 h (a project cut-off, not an official NYC standard)")
    st.caption("Closure is a recorded status, not a measure of citizen satisfaction. "
               "The 72-hour line is a project-defined analytical cut-off.")

    a, b = st.columns(2)
    with a:
        st.subheader("Monthly trend")
        st.plotly_chart(chart("T05", q("T05")), width="stretch")
    with b:
        st.subheader("Top 10 complaint types")
        st.plotly_chart(chart("T02", q("T02")), width="stretch")
    a, b = st.columns(2)
    with a:
        st.subheader("Requests by borough")
        st.plotly_chart(chart("T04", q("T04")), width="stretch")
    with b:
        st.subheader("How long requests take to close")
        st.plotly_chart(chart("T12b", q("T12b")), width="stretch")
    st.subheader("When requests arrive")
    st.plotly_chart(chart("T06", q("T06")), width="stretch")

elif page == "Analyst tasks":
    st.title("The 15 analyst investigations")
    st.caption(filter_label())
    names = [n for n in SQL if n != "KPI"]
    pick = st.selectbox("Investigation", names, format_func=lambda n: f"{n}  {SQL[n]['title']}")
    note = NOTES[pick]
    st.markdown(f"**Question:** {note['question']}")
    df = q(pick)
    st.markdown(f"**Result rows:** {len(df):,}  |  **Requests in filter:** {int(kpi.total_requests[0]):,}")
    if df.empty:
        st.info("This investigation has no rows for the current filters "
                "(e.g. medians need at least 50 closed requests per group).")
    else:
        fig = chart(pick, df)
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
        st.dataframe(df, width="stretch", hide_index=True)
    with st.expander("SQL used"):
        st.code(SQL[pick]["sql"], language="sql")
    st.markdown(f"**Pattern on the full extract:** {note['pattern']}")
    st.markdown(f"**Cautious interpretation:** {note['interpretation']}")
    if F != (str(lo), str(hi + timedelta(days=1)), (), ()):
        st.caption("You have filters on, so the chart and table may differ from the full-extract note above.")

elif page == "Data quality":
    st.title("Data quality checks")
    st.caption(filter_label())
    base, params = Q.build_base(*F[:2], list(boroughs), list(ctypes))
    flag_cols = ["flag_closed_before_created", "flag_zero_duration", "flag_future_date",
                 "flag_status_closed_no_date", "flag_date_but_not_closed", "flag_midnight_created",
                 "flag_missing_coords", "flag_coords_outside_nyc", "flag_unspecified_borough", "res_outlier_iqr"]
    sums = ", ".join(f"SUM({c}) AS {c}" for c in flag_cols)
    flags = safe(run_raw, f"{base} SELECT COUNT(*) AS rows_in_filter, {sums} FROM base", tuple(params))
    t = flags.T.reset_index()
    t.columns = ["check", "rows"]
    t["rows"] = t["rows"].astype(float).fillna(0).astype(int)
    st.dataframe(t, hide_index=True, width="stretch")
    st.markdown("Rows are **flagged, not deleted**. Impossible durations (closed before created) are left out "
                "of resolution statistics only. Full log: `docs/cleaning_log.md`.")
    log = C.DOCS_DIR / "cleaning_log.md"
    if log.exists():
        with st.expander("Cleaning log (full extract)"):
            st.markdown(log.read_text(encoding="utf-8"))
    val = C.DOCS_DIR / "load_validation.md"
    if val.exists():
        with st.expander("MySQL load validation"):
            st.markdown(val.read_text(encoding="utf-8"))

elif page == "Record preview":
    st.title("Filtered record preview")
    st.caption(filter_label())
    n = st.slider("Rows to show", 50, 1000, 200, step=50)
    base, params = Q.build_base(*F[:2], list(boroughs), list(ctypes))
    sql = (f"{base} SELECT unique_key, created_date, closed_date, status, agency, complaint_type, "
           f"descriptor, borough, incident_zip, resolution_hours, is_closed, over_72h "
           f"FROM base ORDER BY created_date DESC LIMIT %s")
    rec = safe(run_raw, sql, tuple(params) + (n,))
    st.dataframe(rec, hide_index=True, width="stretch")
    st.download_button("Download these rows (CSV)", rec.to_csv(index=False), "urban_pulse_preview.csv")

else:
    st.title("About and limitations")
    st.markdown(f"""
**Source:** NYC Open Data, *311 Service Requests from 2020 to Present* ([erm2-nwe9]({C.API_URL.replace('/resource/erm2-nwe9.json', '/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9')})).

**Extract:** 12 months ({C.WINDOW_START} to {C.WINDOW_END}, end excluded), systematic ~3% sample
(request IDs ending 07, 37 or 67), 119,202 requests, pulled on 2026-11-03.

**Limitations**
* 311 counts **reported** requests, not how common a problem really is.
* The live dataset changes daily; these numbers belong to the extraction date.
* Recent months look less closed simply because they had less time.
* Agencies and categories differ in complexity, so durations are not efficiency rankings.
* "Closed" is a recorded status; it does not prove the issue was fixed or the citizen was satisfied.
* The 72-hour cut-off is a project choice, not an official NYC standard.
""")
