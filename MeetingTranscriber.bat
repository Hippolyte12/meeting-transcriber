@echo off
title Meeting Transcriber
cd /d "%~dp0"

REM Vérifier que Python embarqué est présent
if not exist "python_embed\python.exe" (
    echo ============================================================
    echo   ERREUR : Python embarque introuvable.
    echo   Reinstallez l'application.
    echo ============================================================
    pause
    exit /b 1
)

REM Premier lancement : installer les dépendances
if not exist ".installed" (
    echo Premier lancement - installation des dependances...
    echo Cela peut prendre 5-10 minutes, merci de patienter.
    echo.
    python_embed\python.exe setup_first_run.py
    if %ERRORLEVEL% neq 0 (
        echo Erreur lors de l'installation.
        pause
        exit /b 1
    )
)

REM Lancer l'application
echo Demarrage de Meeting Transcriber...
echo L'interface s'ouvrira dans votre navigateur a l'adresse :
echo http://127.0.0.1:7860
echo.
echo Ne fermez pas cette fenetre pendant l'utilisation.
echo.
start "" /B cmd /C "timeout /t 4 /nobreak >nul && start http://127.0.0.1:7860"
python_embed\python.exe -I app.py

pause