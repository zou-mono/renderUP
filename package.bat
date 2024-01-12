@echo off
pushd "%~dp0"
cd ..

for %%i in ("%CD%") do set curfolder=%%~fsi

call python-qgis-ltr -m pyarmor.cli gen -O dist -r -i renderup --exclude renderup/resources_rc.py --exclude renderup/__pycache__

REM copy addition files
echo %curfolder%
echo %~dp0
call copy "%~dp0\metadata.txt" "%curfolder%\dist\renderup\metadata.txt"
call copy "%~dp0\extramaps.yml" "%curfolder%\dist\renderup\extramaps.yml"
call copy "%~dp0\resources_rc.py" "%curfolder%\dist\renderup\resources_rc.py"
echo "package success."

popd