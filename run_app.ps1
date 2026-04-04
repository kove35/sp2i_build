$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = "C:\Users\Geoffrey\AppData\Local\Programs\Python\Python311\python.exe"

Write-Host "Demarrage du backend FastAPI..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$projectRoot'; & '$pythonPath' -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000"
)

Start-Sleep -Seconds 2

Write-Host "Demarrage du frontend Streamlit..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$projectRoot'; & '$pythonPath' -m streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501"
)

Write-Host ""
Write-Host "Application SP2I_Build lancee." -ForegroundColor Green
Write-Host "Python   : $pythonPath"
Write-Host "API      : http://127.0.0.1:8000"
Write-Host "Frontend : http://127.0.0.1:8501"
