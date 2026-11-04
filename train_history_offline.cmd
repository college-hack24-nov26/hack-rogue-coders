@echo off
setlocal
call "%~dp0train_offline.cmd" --data-mode simulation --simulation-dataset "%~dp0data\raw\supply\history-simulation" --output "%~dp0artifacts\supply-history-models" %*
exit /b %ERRORLEVEL%
