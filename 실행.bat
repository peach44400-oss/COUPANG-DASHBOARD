@echo off
chcp 65001 >nul
title 쿠팡 통합 대시보드
cd /d "%~dp0"
start "" http://127.0.0.1:8700
python app\main.py
pause
