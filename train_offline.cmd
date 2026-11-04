@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo The local Python environment is missing. Install the project dependencies before going offline.
    popd
    exit /b 1
)
".venv\Scripts\python.exe" -m scripts.train_supply_offline %*
set "TRAIN_RESULT=%ERRORLEVEL%"
popd
exit /b %TRAIN_RESULT%
