@echo off
title CogniPulse API Server

cd /d "%~dp0\llama"

llama-server.exe -m "..\model\CogniPulse.gguf" -c 2048 --host 0.0.0.0 --port 8080 --temp 0.65 --top-k 5 -n 64 --repeat-penalty 1.1 --repeat-last-n 256
pause