@echo off
cd /d "%~dp0"
call "%~dp0venv\Scripts\activate"
python merge_lore.py
pause