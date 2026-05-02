@echo off
REM Launch the H-1B Landscape Streamlit app from the project's venv.
REM Usage: double-click this file, or run from this folder.

cd /d "%~dp0"
echo Starting Streamlit on http://localhost:8501 ...
".venv\Scripts\streamlit.exe" run app.py
pause
