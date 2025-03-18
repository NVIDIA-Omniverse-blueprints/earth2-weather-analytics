@echo off

call "%~dp0..\..\..\..\repo.bat" ci test
if %errorlevel% neq 0 ( exit /b %errorlevel% )
