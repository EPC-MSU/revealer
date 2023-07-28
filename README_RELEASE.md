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

* Чтобы полученный исполняемый файл запускался на других компьютерах не требовал смены типа на "executable", нужно заархивировать полученную при сборке папку _release_ в архив формата _tar_.

### Выпуск релиза в MacOS

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

6. Полученные релизы выложить на сетевой диск в папку Z:\UltraRay\uRPC\Релизы\revealer и написать changelog к версии с важнейшими изменениями.





