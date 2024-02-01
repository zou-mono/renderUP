@echo off
pushd "%~dp0"
cd ..

for %%i in ("%CD%") do set curfolder=%%~fsi

rmdir /q /s "%curfolder%\dist"

call python-qgis-ltr -m pyarmor.cli gen --platform windows.x86_64 --platform darwin.x86_64 -O dist -r -i renderup --exclude renderup/__init__.py --exclude renderup/resources_rc.py --exclude renderup/__pycache__

REM copy addition files
echo %curfolder%
echo %~dp0
call copy "%~dp0\metadata.txt" "%curfolder%\dist\renderup\metadata.txt"
call copy "%~dp0\extramaps.yml" "%curfolder%\dist\renderup\extramaps.yml"
call copy "%~dp0\resources_rc.py" "%curfolder%\dist\renderup\resources_rc.py"
call copy "%~dp0\__init__.py" "%curfolder%\dist\renderup\__init__.py"

mkdir "%curfolder%\dist\renderup\icons\"
call copy "%~dp0\icons\icon.png" "%curfolder%\dist\renderup\icons\icon.png"
call copy "%~dp0\icons\metro_station.svg" "%curfolder%\dist\renderup\icons\metro_station.svg"

7z a -r "%curfolder%\dist\renderup.zip" "%curfolder%\dist\renderup\"

echo "package success."

popd