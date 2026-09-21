@echo off
chcp 65001 >nul
title Mercek

REM Kurulum bittikten sonra uygulamayi tek tiklamayla ayaga kaldirir:
REM Qdrant + backend + arayuz, ardindan tarayiciyi acar.
REM Ilk kurulum icin KURULUM.md dosyasina bakin.

cd /d "%~dp0"

echo.
echo   Mercek baslatiliyor...
echo.

REM --- On kosullar -------------------------------------------------------
if not exist "backend\.venv\Scripts\activate.bat" (
    echo   [HATA] backend\.venv bulunamadi.
    echo          Once kurulumu tamamlayin: KURULUM.md, Adim 4a-4b.
    echo.
    pause
    exit /b 1
)
if not exist "frontend\node_modules" (
    echo   [HATA] frontend\node_modules bulunamadi.
    echo          frontend klasorunde "npm install" calistirin.
    echo.
    pause
    exit /b 1
)

REM --- Qdrant ------------------------------------------------------------
echo   [1/3] Qdrant kontrol ediliyor...
docker compose up -d qdrant >nul 2>&1
if errorlevel 1 (
    echo   [HATA] Qdrant baslatilamadi. Docker Desktop acik mi?
    echo.
    pause
    exit /b 1
)

REM --- Backend ve arayuz -------------------------------------------------
REM start /d ile calisma dizini verilir; boylece yolda bosluk olsa bile
REM ic ice tirnak sorunu cikmaz.
echo   [2/3] Backend baslatiliyor (ayri pencere)...
start "Mercek backend" /d "%~dp0backend" cmd /k ".venv\Scripts\activate.bat && uvicorn app.main:app --reload"

echo   [3/3] Arayuz baslatiliyor (ayri pencere)...
start "Mercek arayuz" /d "%~dp0frontend" cmd /k "npm run dev"

REM Vite'in portu acmasini bekle, sonra tarayiciyi ac.
timeout /t 6 /nobreak >nul
start "" http://localhost:5173

echo.
echo   Hazir. Arayuz: http://localhost:5173
echo.
echo   Ilk analizde gomme modeli bellege alinirken 1-3 dakika beklenir.
echo   Kapatmak icin acilan iki pencerede Ctrl+C, sonra:
echo     docker compose stop qdrant
echo.
pause
