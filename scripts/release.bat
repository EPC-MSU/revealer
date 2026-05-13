set PYTHON=python
python -c "import struct; print(8 * struct.calcsize(\"P\"))" > result.txt
set /p target_platform=<result.txt
echo %target_platform%
del result.txt
echo %target_platform%

cd ..
if exist build rd /S /Q build
if exist dist rd /S /Q dist
if exist release rd /S /Q release
if exist venv rd /S /Q venv
%PYTHON% -m venv venv
venv\Scripts\python -m pip install --upgrade pip
venv\Scripts\python -m pip install -r requirements.txt
venv\Scripts\python -m pip install pyinstaller
venv\Scripts\pyinstaller main.py --clean --onefile --noconsole ^
--add-data "resources\*;resources" ^
--icon resources\appicon.ico

rename dist release
cd release
rename main.exe revealer.exe
cd ..
if exist build rd /S /Q build
if exist dist rd /S /Q dist
if exist venv rd /S /Q venv
if exist *.spec del *.spec
cd scripts
pause
