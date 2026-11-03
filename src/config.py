"""Shared settings for the Urban Pulse NYC pipeline.

Database credentials are read from environment variables (or a local .env
file that is never shared). Nothing secret is written in the code.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

# ---------- folders ----------
RAW_DIR = PROJECT_ROOT / "data" / "raw"
CLEAN_DIR = PROJECT_ROOT / "data" / "clean"
DOCS_DIR = PROJECT_ROOT / "docs"
FIG_DIR = PROJECT_ROOT / "reports" / "figures"
for d in (RAW_DIR, CLEAN_DIR, DOCS_DIR, FIG_DIR):
    d.mkdir(parents=True, exist_ok=True)

RAW_CSV = RAW_DIR / "nyc311_raw.csv"
RAW_META = RAW_DIR / "extraction_metadata.json"
CLEAN_CSV = CLEAN_DIR / "nyc311_clean.csv"

# ---------- API ----------
API_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
APP_TOKEN = os.getenv("SOCRATA_APP_TOKEN", "")  # optional, raises rate limits

# Extraction window: 12 full months (start inclusive, end exclusive)
WINDOW_START = "2025-11-01"
WINDOW_END = "2026-11-01"

# Systematic sample: keep requests whose unique_key ends in one of these
# two-digit endings. Each ending is ~1% of all requests, so 3 endings ~= 3%,
# which gives roughly 100k rows for a year of NYC 311 data.
KEY_SUFFIXES = ["07", "37", "67"]

PAGE_SIZE = 5000      # rows per API call
TIMEOUT_S = 120       # seconds before an API call is abandoned
MAX_RETRIES = 5       # retries for temporary API failures

# The 25 source fields we keep (checked against the live API schema)
FIELDS = [
    "unique_key", "created_date", "closed_date", "due_date",
    "resolution_action_updated_date", "agency", "agency_name",
    "complaint_type", "descriptor", "location_type", "status",
    "resolution_description", "borough", "incident_zip", "city",
    "incident_address", "street_name", "address_type", "community_board",
    "council_district", "police_precinct", "open_data_channel_type",
    "park_borough", "latitude", "longitude",
]

# ---------- MySQL ----------
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "urban_pulse_db")
TABLE = "service_requests"
STAGING_TABLE = "service_requests_staging"

# ---------- analysis ----------
SLA_HOURS = 72   # project-defined cut-off, NOT an official NYC standard


def mysql_url(with_db: bool = True) -> str:
    """SQLAlchemy connection string built from environment variables."""
    from urllib.parse import quote_plus
    db = f"/{MYSQL_DB}" if with_db else "/"
    return (f"mysql+pymysql://{MYSQL_USER}:{quote_plus(MYSQL_PASSWORD)}"
            f"@{MYSQL_HOST}:{MYSQL_PORT}{db}?charset=utf8mb4")
