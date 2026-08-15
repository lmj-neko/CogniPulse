@echo off
cd /d "%~dp0"
call "%~dp0venv\Scripts\activate"
pip install -r requirements.txt
pause