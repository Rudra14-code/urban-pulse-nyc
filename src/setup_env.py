"""One-time helper: asks for the MySQL password, tests it, saves it to .env.

.env stays on this computer only (it is listed in .gitignore).
"""
import getpass
from pathlib import Path

import pymysql

root = Path(__file__).resolve().parents[1]
user = "root"
pw = getpass.getpass("MySQL root password: ")
try:
    pymysql.connect(host="localhost", port=3306, user=user, password=pw).close()
except Exception as e:
    print("Connection failed:", e)
    raise SystemExit(1)
(root / ".env").write_text(
    f"MYSQL_HOST=localhost\nMYSQL_PORT=3306\nMYSQL_USER={user}\n"
    f"MYSQL_PASSWORD={pw}\nMYSQL_DB=urban_pulse_db\n")
print("Connected OK. Saved .env")
