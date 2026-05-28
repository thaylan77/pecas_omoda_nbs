# Script de inicialização dos servidores do Importador NBS
Write-Host "Iniciando servidores locais do Importador NBS..." -ForegroundColor Cyan

# 1. Iniciar o Backend FastAPI em um novo terminal PowerShell
Write-Host "Iniciando Backend FastAPI (Porta 8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; python -m uvicorn main:app --reload --port 8000"

# 2. Iniciar o Frontend React em um novo terminal PowerShell
Write-Host "Iniciando Frontend React (Vite)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Write-Host "Servidores iniciados! Acesse http://localhost:5173 no seu navegador." -ForegroundColor Green
