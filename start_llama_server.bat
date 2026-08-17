@echo off
title CogniPulse API Server Launcher

cd /d "%~dp0\llama"

start "CogniPulse_Chat" cmd /c "llama-server.exe -m ..\model\CogniPulse_Chat_v0.2.gguf -c 2048 --host 0.0.0.0 --port 8080 --temp 0.65 --top-k 5 -n 64 --repeat-penalty 1.1 --repeat-last-n 256 & pause"

start "CogniPulse_Work" cmd /c "llama-server.exe -m ..\model\CogniPulse_Work_v0.gguf -c 2048 --host 0.0.0.0 --port 8081 --temp 0.65 --top-k 5 -n 64 --repeat-penalty 1.1 --repeat-last-n 256 & pause"