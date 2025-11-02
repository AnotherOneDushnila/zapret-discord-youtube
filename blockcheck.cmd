@echo off

cd /d "%~dp0"
FOR /F "tokens=* USEBACKQ" %%F IN (`bin\hide\cygwin\bin\cygpath -C OEM -a -m blockcheck\files\blog.sh`) DO (
set P='%%F'
)

"%~dp0\bin\hide\elevator.exe" bin\hide\cygwin\bin\bash.exe -i "%P%"

