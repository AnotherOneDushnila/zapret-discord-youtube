@echo off

cd /d "%~dp0"
FOR /F "tokens=* USEBACKQ" %%F IN (`bin\cygwin\bin\cygpath -C OEM -a -m blockcheck\files\blog.sh`) DO (
SET P='%%F'
)

"%~dp0\bin\elevator.exe" bin\cygwin\bin\bash.exe -i "%P%"

@REM reg Query "HKLM\Hardware\Description\System\CentralProcessor\0" | find /i "x86" > NUL && set "OS=32BIT" || set "OS=64BIT"

@REM if %OS%=="32BIT" (
@REM     del /f "%~dp0\bin\custom\PossibleStarts64.exe"
@REM ) else (
@REM     del /f "%~dp0\bin\custom\PossibleStarts32.exe"
@REM )

