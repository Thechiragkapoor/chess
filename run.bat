@echo off
setlocal

:: Define image name
set IMAGE_NAME=chess-auto-streamer

:: Build Docker image
echo Building Docker image...
docker build -t %IMAGE_NAME% .

:: Run Docker container
echo Running Docker container...
docker run --rm --memory=512m %IMAGE_NAME%

pause
