@echo off
chcp 65001 > nul
:: 65001 - UTF-8

cd /d "%~dp0"
call service.bat status_zapret
call service.bat load_hide_switch
call service.bat load_game_filter
echo:

set "BIN=%~dp0bin\%HideSwitchStatus%\"
set "FAKE=%~dp0fake\"
set "LISTS=%~dp0lists\"

start "zapret: %~n0" /min "%BIN%winws.exe" --wf-tcp=80,443,%GameFilter% --wf-udp=443,%GameFilter% ^
--filter-tcp=2053,2083,2087,2096,8443 --hostlist-domains=discord.media --dpi-desync=multisplit --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-split-seqovl-pattern="%FAKE%tls_clienthello_www_google_com.bin" --new ^
--filter-tcp=443 --hostlist="%LISTS%list-general.txt" --dpi-desync=multisplit --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-split-seqovl-pattern="%FAKE%tls_clienthello_www_google_com.bin" --new ^
--filter-udp=1400,19294-19344,50000-50100 --filter-l7=discord,stun --dpi-desync=fake --dpi-desync-repeats=6 --new ^
--filter-udp=1400 --filter-l7=stun --dpi-desync=fake --dpi-desync-repeats=6 --new ^
--filter-tcp=2099 --ipset="%LISTS%ipset-cloudflare.txt" --dpi-desync=syndata --new ^
--filter-tcp=5222 --ipset="%LISTS%ipset-cloudflare.txt" --dpi-desync=syndata --new ^
--filter-tcp=5223 --ipset="%LISTS%ipset-cloudflare.txt" --dpi-desync=syndata 

