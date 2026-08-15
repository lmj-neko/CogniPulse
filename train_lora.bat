@echo off
cd /d "%~dp0"
call "%~dp0venv\Scripts\activate"
python train_lora.py
pause