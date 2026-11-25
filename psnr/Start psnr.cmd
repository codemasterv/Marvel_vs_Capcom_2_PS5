@echo off
netsh advfirewall firewall add rule name="psnr TCP" dir=in action=allow protocol=TCP localport=36100,36101
netsh advfirewall firewall add rule name="psnr UDP" dir=in action=allow protocol=UDP localport=36100
cd /d "%~dp0server"
start "" http://127.0.0.1:36101/
psnr.exe -http 0.0.0.0:36101 -v