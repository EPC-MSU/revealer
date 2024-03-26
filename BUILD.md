# Сборка revealer

### Сборка под Windows

2. Для выпуска релиза в Windows нужно выполнить скрипт `release.bat`:

```
release.bat
```

__Обратите внимание__: для корректного запуска собранного приложения на Windows 7 без установленного python релиз необходимо собирать на компьютере с __Windows 7__. Иначе будут ошибки с отсутствием исходных библиотек (python36.dll, api-ms-win-crt-runtime-l1-1-0.dll).

### Сборка под Linux

2. Для выпуска релиза в Linux нужно выполнить скрипт `release.sh`:

Обратите внимание, что для запуска скрипта в Linux могут потребоваться дополнительные действия:
* Добавьте `release.sh` права на запуск:
```bash
chmod +x ./release.sh
```
* Установите версию python3 c встроенным модулем tkinter:
```bash
sudo apt-get install python3-tk
```
* Установите версию python3 с поддержкой виртуальных кружений:
```bash
sudo apt-get install python3-venv
```

* Установите стандартную библиотеку idle:
```bash
sudo apt-get install idle3
```

* Запустите скрипт сборки:
```
bash release.sh
```

### Сборка под macOS

Для выпуска релиза в MacOS нужно выполнить скрипт `release_macos.sh`:

```bash
sudo ./release_macos.sh
```

Обратите внимание, что для запуска скрипта в MacOS могут потребоваться дополнительные действия:
* Установите версию python3 c встроенным модулем tkinter (для mac OS tkinter поддерживается в версии python3.9 и старше):
```bash
brew install python-tk@3.9
```
* Сборка приложения на macOS (папка с расширением .app, а не просто испольняемый файл) делается с помощью модуля _py2app_, который явным образом не добавляет библиотеку tkinter в библиотеку собранного приложения. Чтобы запуск приложения был возможен на всех системах, а  не только там, где установлен python с tkinter, исходные файлы библиотеки явным образом копируются в виртуальное окружение в `release_macos.sh` с помощью команд:
```bash
cp -R /Library/Frameworks/Python.framework/Versions/3.9/lib/tcl8.6/ venv/lib/tcl8.6
cp -R /Library/Frameworks/Python.framework/Versions/3.9/lib/tcl8/ venv/lib/tcl8
cp -R /Library/Frameworks/Python.framework/Versions/3.9/lib/tk8.6/ venv/lib/tk8.6
```

Если на машине, где вы собираете приложение путь до библиотеки tkinter иной, то его нужно заменить. Чтобы его узнать запустите python3 из терминала и введите:
```bash
import tkinter
root = tkinter.Tk()  # the window will show up - close it
print(root.tk.exprstring('$tcl_library'))   # replace /Library/Frameworks/Python.framework/Versions/3.9/lib/tcl8.6/ with this path
print(root.tk.exprstring('$tk_library'))  # replace /Library/Frameworks/Python.framework/Versions/3.9/lib/tk8.6/ venv/lib/tk8.6 with this path
```
А также поменяйте путь к /tcl8/ с аналогичным началом (_/Library/Frameworks/Python.framework/Versions/3.9/lib/_), как те, что выведет вам _print_ выше.






