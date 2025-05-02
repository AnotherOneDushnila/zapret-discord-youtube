@echo off
setlocal enabledelayedexpansion



if "%1"=="admin" (
    echo Started with admin rights
) else (
    echo Requesting admin rights...
    powershell -Command "Start-Process 'cmd.exe' -ArgumentList '/c \"\"%~f0\" admin\"' -Verb RunAs"
    exit /b
)

set "STARTUP_PATH=%USERPROFILE%\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup"

cd /d "%~dp0"

echo Pick one of the options:
set "count=0"
for %%f in (*.bat) do (
    set "filename=%%~nxf"
    if /i not "!filename:~0,7!"=="service" if /i not "!filename:~0,17!"=="cloudflare_switch" (
        set /a count+=1
        echo !count!. %%f
        set "file!count!=%%f"
    )
)

:: Choosing file
set "choice="
set /p "choice=Input file index (number): "
if "!choice!"=="" (
    echo Invalid choice, exiting...
    pause
    exit /b
)

set "selectedFile=!file%choice%!"
if not defined selectedFile (
    echo Invalid choice, exiting...
    pause
    exit /b
)

cd %STARTUP_PATH%

if exist "%STARTUP_PATH%\!selectedFile!" (
    echo Deleting existing file...
    del /f "%STARTUP_PATH%\!selectedFile!"
    if errorlevel 1 (
        echo Failed to delete file
    ) else (
        echo File deleted successfully
    )
) else (
    copy "%~dp0!selectedFile!" "%STARTUP_PATH%"
    if errorlevel 1 (
        echo Failed to copy file
    ) else (
        echo File copied successfully
    )
)

pause