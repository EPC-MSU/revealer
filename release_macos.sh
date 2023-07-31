rm -rf build
rm -rf dist
rm -rf release
rm -rf venv
rm -rf setup.py

python3 -m venv venv
cp -R /Library/Frameworks/Python.framework/Versions/3.9/lib/tcl8.6/ venv/lib/tcl8.6
cp -R /Library/Frameworks/Python.framework/Versions/3.9/lib/tcl8/ venv/lib/tcl8
cp -R /Library/Frameworks/Python.framework/Versions/3.9/lib/tk8.6/ venv/lib/tk8.6
./venv/bin/python3 -m pip install --upgrade pip
./venv/bin/python3 -m pip install -r requirements.txt
./venv/bin/python3 -m pip install py2app==0.28.6
./venv/bin/py2applet --make-setup main.py ./resources/appicon.icns
./venv/bin/python3 setup.py py2app --resources ./resources 

cp ./README.md ./dist/readme.md
mv dist release
mv ./release/main.app ./release/revealer.app

rm -rf build
rm -rf dist
rm -rf venv
rm -rf setup.py