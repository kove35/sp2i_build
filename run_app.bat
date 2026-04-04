@echo off
cd /d "%~dp0"
set "SP2I_PYTHON=C:\Users\Geoffrey\AppData\Local\Programs\Python\Python311\python.exe"

echo Demarrage du backend FastAPI...
start "SP2I Backend" powershell -NoExit -Command "cd '%~dp0'; & '%SP2I_PYTHON%' -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000"

timeout /t 2 /nobreak >nul

echo Demarrage du frontend Streamlit...
start "SP2I Frontend" powershell -NoExit -Command "cd '%~dp0'; & '%SP2I_PYTHON%' -m streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501"

echo.
echo Application SP2I_Build lancee.
echo Python   : %SP2I_PYTHON%
echo API      : http://127.0.0.1:8000
echo Frontend : http://127.0.0.1:8501
