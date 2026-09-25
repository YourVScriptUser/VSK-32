@echo off

where python >nul 2>&1
if %errorlevel% == 0 (
    set "PYTHON=py"
) else (
    where py >nul 2>&1
    if %errorlevel% == 0 (
        set "PYTHON=python"
    ) else (
        echo Python was not found.
        exit /b 1
    )
)

cd /d "%~dp0.."
%PYTHON% Assembler/x32sm.py %*
