rm -rf build
rm -rf dist
rm -rf release
rm -rf venv

python3 -m venv venv
./venv/bin/python3 -m pip install --upgrade pip
./venv/bin/python3 -m pip install -r requirements.txt
./venv/bin/python3 -m pip install pyinstaller
./venv/bin/pyinstaller main.py --clean --onefile --noconsole \
--add-data "./resources/*:resources" \
--icon resources/appicon.icns

cp ./README.md ./dist/readme.md
mv dist release
mv ./release/main ./release/revealer
rm -rf build
rm -rf dist
rm -rf venv

