@echo off
title SmartOps CLI
cd /d "%~dp0"

rem 1) ambiente virtual da propria pasta
set "PY=.venv\Scripts\python.exe"
if exist "%PY%" goto rodar

rem 2) ambiente do projeto vizinho (conveniencia no ambiente de desenvolvimento)
set "PY=..\Projeto-1-Minecraft\.venv\Scripts\python.exe"
if exist "%PY%" goto rodar

rem 3) Python instalado no sistema
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo Python nao encontrado.
    echo Instale o Python 3.12 em https://www.python.org/downloads/
    echo marcando "Add python.exe to PATH" e rode de novo.
    echo.
    pause
    exit /b 1
)
set "PY=python"

:rodar
"%PY%" main.py %*
echo.
pause
