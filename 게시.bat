@echo off
chcp 65001 >nul
setlocal
title 쿠팡 대시보드 새 버전 게시

REM ── 새 버전 게시 ──────────────────────────────────────
REM  1) app\main.py 의 APP_VERSION 을 올리고
REM  2) version.json 의 "version"·"notes" 를 맞춘 뒤
REM  3) 이 배치 실행: 빌드 → GitHub Release 생성 → exe·version.json 업로드
REM  * GitHub CLI(gh) 설치·로그인 필요:  gh auth login
REM ──────────────────────────────────────────────────────

for /f "usebackq tokens=2 delims=:, " %%v in (`findstr /i "\"version\"" version.json`) do set VER=%%~v
if "%VER%"=="" ( echo [오류] version.json 에서 version 을 읽지 못했습니다. & pause & exit /b 1 )
echo 게시할 버전: v%VER%
echo.

echo [1/3] exe 빌드 중...
python -m PyInstaller --noconfirm --clean CoupangDash.spec
if not exist "dist\쿠팡대시보드.exe" ( echo [오류] 빌드 실패 - dist\쿠팡대시보드.exe 없음 & pause & exit /b 1 )

echo.
echo [2/3] GitHub Release 생성 (v%VER%)...
REM 릴리스 자산은 영문 파일명으로 — 한글 파일명은 릴리스에서 깨짐
copy /y "dist\쿠팡대시보드.exe" "dist\CoupangDash.exe" >nul
gh release create "v%VER%" "dist\CoupangDash.exe" "version.json" --title "v%VER%" --notes-file version.json
if errorlevel 1 ( echo [오류] Release 생성 실패. gh 로그인 확인:  gh auth status & pause & exit /b 1 )

echo.
echo [3/3] 정리...
rmdir /s /q build 2>nul

echo.
echo ============================================
echo  v%VER% 게시 완료!
echo  각 PC의 프로그램에서 [업데이트 - 업데이트 확인]을 누르면 받아집니다.
echo ============================================
pause
