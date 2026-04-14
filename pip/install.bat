@echo off
setlocal
pushd "%~dp0.."
echo Installing RawView in editable mode from:
cd
pip install -e .
set ERR=%ERRORLEVEL%
popd
exit /b %ERR%
