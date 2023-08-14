# Revealer

Программа для поиска сетевых устройств в локальной сети.

## Выпуск релиза

1. Убедитесь, что в репозитории нет несохраненных изменений и все они отправлены в удаленный репозиторий.
2. На коммит, из которого планируется выпускать версию нужно повесить тег в формате __v#.#.#__, где #.#.# - номер версии.
3. Не забыть отправить тег в удаленный репозиторий.
4. Увеличить версию в файле _version.py_.

### Выпуск релиза в Windows

5. Для выпуска релиза в Windows нужно выполнить скрипт `release.bat`:

```bash
release.bat
```

__Обратите внимание__: для корректного запуска на Windows 7 без установленного python релиз необходимо собирать на компьютере с __Windows 7__. Иначе будут ошибки с отсутствием исходных библиотек (python36.dll, api-ms-win-crt-runtime-l1-1-0.dll).

### Выпуск релиза в Linux

5. Для выпуска релиза в Linux нужно выполнить скрипт `release.sh`:

```bash
bash release.sh
```

Обратите внимание, что для запуска скрипта в Linux могут потребоваться дополнительные действия:
* Добавьте `release.sh` права на запуск:
```bash
chmod +x ./release.sh
```
* Установите версию python3 c встроенным модулем tkinter:
```bash
sudo apt-get install python3.8-tk
```
* Установите версию python3 с поддержкой виртуальных кружений:
```bash
sudo apt-get install python3.8-venv
```

* Установите стандартную библиотеку idle:
```bash
sudo apt-get install idle3
```

* Чтобы полученный исполняемый файл запускался на других компьютерах не требовал смены типа на "executable", нужно заархивировать полученную при сборке папку _release_ в архив формата _tar.gz_. Чтобы сжать полученные два файла в такой архив нужно перейти в полученную в результате сборки папку release и выполнить команду сжатия:
```bash
cd release
tar -czvf revealer-X.Y.Z-ubuntu64.tar.gz readme.md revealer
```
Вместо X.Y.Z укажите версию вашего релиза.

### Выпуск релиза в MacOS

Для выпуска использовалась виртуальная машина _MacOS_1012_vb51_ (с сетевого диска Z:\Distr\VirtualBox Images) с установленным python3.9.8 (согласно рекомендации с https://www.python.org/download/mac/tcltk/ для использования со встроенным tkinter, в нем стоит версия Tkinter 8.6.8). Версии устанавливаемых модулей:
ifaddr = 0.2.0
py2app = 0.28.6
pip = 23.2.1

5. Для выпуска релиза в MacOS нужно выполнить скрипт `release_macos.sh`:

```bash
sudo ./release_macos.sh
```

Обратите внимание, что для запуска скрипта в MacOS могут потребоваться дополнительные действия:
* Установите версию python3 c встроенным модулем tkinter (для mac OS tkinter поддерживается в версии python3.9 и старше):
```bash
brew install python-tk@3.9
```
* Сборка приложения на macOS (папка с расширением .app, а не просто испольняемый файл) делается с помощью модуля _py2app_, который явным образом не добавляет библиотеку tkinter в библиотеку собранного приложения. Чтобы запуск приложения было возможно на всех системах, а  не только там, где установлен python с tkinter исходные файлы библиотеки явным образом копируются в виртуальное окружение в `release_macos.sh` с помощью команд:
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

__Важно__: полученное таким образом приложение для macOS с расширением _.app_ нужно запокавать в zip-архив на __той же системе, где проводилась сборка__, иначе файлы внутри приложения могут побиться (при переносе на другую ОС) и в итоге приложение из такого архива запускаться не будет.

6. Полученные релизы выложить на сетевой диск в папку Z:\UltraRay\uRPC\Релизы\revealer и написать changelog к версии с важнейшими изменениями.





