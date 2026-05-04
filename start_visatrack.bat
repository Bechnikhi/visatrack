@echo off
title VisaTrack - Lanceur
color 0A

echo.
echo  ██╗   ██╗██╗███████╗ █████╗ ████████╗██████╗  █████╗  ██████╗██╗  ██╗
echo  ██║   ██║██║██╔════╝██╔══██╗╚══██╔══╝██╔══██╗██╔══██╗██╔════╝██║ ██╔╝
echo  ╚██╗ ██╔╝██║███████╗███████║   ██║   ██████╔╝███████║██║     █████╔╝
echo   ╚████╔╝ ██║╚════██║██╔══██║   ██║   ██╔══██╗██╔══██║██║     ██╔═██╗
echo    ╚═══╝  ╚═╝███████║██║  ██║   ██║   ██║  ██║██║  ██║╚██████╗██║  ██╗
echo.
echo  Lancement de la plateforme...
echo.

cd /d C:\Users\askia\Desktop\visatrack

echo [1/3] Lancement de Django...
start "VisaTrack - Django" cmd /k "cd /d C:\Users\askia\Desktop\visatrack && venv\Scripts\activate && python manage.py runserver && pause"

timeout /t 3 /nobreak > nul

echo [2/3] Lancement de Celery Worker...
start "VisaTrack - Worker" cmd /k "cd /d C:\Users\askia\Desktop\visatrack && venv\Scripts\activate && celery -A config worker -l info -Q monitoring,alerts --pool=solo --pool=solo && pause"

timeout /t 3 /nobreak > nul

echo [3/3] Lancement de Celery Beat...
start "VisaTrack - Beat" cmd /k "cd /d C:\Users\askia\Desktop\visatrack && venv\Scripts\activate && celery -A config beat -l info && pause"

timeout /t 5 /nobreak > nul

echo.
echo  ✅ VisaTrack est lance !
echo.
echo  Admin local  : http://localhost:8000/admin
echo  Email        : admin@visatrack.app
echo  Mot de passe : Admin@1234
echo.
echo  Admin en ligne : https://visatrack-3ngv.onrender.com/admin
echo.
echo  Appuyez sur une touche pour ouvrir le navigateur...
pause > nul

start chrome http://localhost:8000/admin

