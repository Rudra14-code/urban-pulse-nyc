@echo off
rem Starts the Urban Pulse NYC dashboard (MySQL must be running)
cd /d "%~dp0"
".venv\Scripts\streamlit.exe" run app\streamlit_app.py --server.port 8520
pause
