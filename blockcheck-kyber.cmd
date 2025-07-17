@echo off

cd /d "%~dp0"
FOR /F "tokens=* USEBACKQ" %%F IN (`bin\cygwin\bin\cygpath -C OEM -a -m blockcheck\files\blog_kyber.sh`) DO (
SET P='%%F'
)

"%~dp0\bin\elevator.exe" bin\cygwin\bin\bash.exe -i "%P%"
