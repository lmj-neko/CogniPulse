@echo off
cd /d "%~dp0"
call venv\Scripts\activate
set PYTHONPATH=llama.cpp\gguf-py;%PYTHONPATH%
python convert_hf_to_gguf.py ./merged_model --outfile ./merged_f16.gguf --outtype f16
pause