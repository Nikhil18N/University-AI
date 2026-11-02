@echo off
echo ========================================================
echo  Starting Cloudflare Tunnel for University AI Backend
echo ========================================================
echo Forwarding public HTTPS traffic to http://localhost:8080...
echo.
cloudflared tunnel --url http://localhost:8080
pause
