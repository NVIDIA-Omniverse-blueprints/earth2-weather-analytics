@echo off

call "%~dp0..\..\..\..\repo.bat" ci build
if %errorlevel% neq 0 ( exit /b %errorlevel% )
