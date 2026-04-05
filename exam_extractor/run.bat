@echo off
chcp 65001 > nul
title 기출문제 추출기
echo.
echo  ⚡ 기출문제 추출기 시작
echo  ─────────────────────────────────────────
echo.

echo  [1/2] 패키지 설치 중...
pip install -r requirements.txt -q
if errorlevel 1 (
  echo  ❌ 패키지 설치 실패
  pause
  exit /b
)

echo  [2/2] 서버 시작: http://localhost:5050
echo.
timeout /t 2 /nobreak > nul
start http://localhost:5050
python app.py
pause
