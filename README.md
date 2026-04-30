# revealer

A program for discovering network devices on a local network via SSDP / UPnP.

## Support

Windows, Linux, macOS.

## Usage

1. Choose the application for your operating system and launch it.
2. Click the `Search` button to get / refresh the list of discovered network devices that support SSDP.

    ![image](https://raw.githubusercontent.com/EPC-MSU/revealer/dev-2.0/documentation/images/search.png)
3. In the resulting list, available devices on the same local network as your computer will have a clickable link (blue with underline) in the `URL / IP` column. These pages can be opened by left-clicking the corresponding cell in the `URL / IP` column.

    ![image](https://raw.githubusercontent.com/EPC-MSU/revealer/dev-2.0/documentation/images/ready_list.png)
4. To the right of the links, each row has a device info icon (![image](https://raw.githubusercontent.com/EPC-MSU/revealer/dev-2.0/resources/properties.png)) — clicking it opens the list of properties for that device.

    ![image](https://raw.githubusercontent.com/EPC-MSU/revealer/dev-2.0/documentation/images/device_info.png)
5. For devices that are not accessible from your computer (on a different subnet), the `URL / IP` column will show only their IP address, and the device info list will be shorter, since `revealer` cannot retrieve a full device description via an HTTP request to the `Location` URL.

    ![image](https://raw.githubusercontent.com/EPC-MSU/revealer/dev-2.0/documentation/images/device_info_not_local.png)
6. For devices that support it, you can change the IP address using the extended SSDP protocol. To do so:
    * Click the two-gears icon (![image](https://raw.githubusercontent.com/EPC-MSU/revealer/dev-2.0/resources/settings2.png)) to open the `Change settings...` window. If this option is unavailable, the device version does not support it.
    
        ![image](https://raw.githubusercontent.com/EPC-MSU/revealer/dev-2.0/documentation/images/device_change_settings.png)
    * In the window that opens, enter the device password, check or uncheck DHCP (dynamic network configuration from a DHCP server), and specify the desired IP address, subnet mask, and optionally the default gateway.
    * Click `Ok`.
    * After a moment, a result window will appear: if the password and settings were accepted by the device, the result will be `Success` — otherwise an `Error` window will appear.
    * If the settings were sent successfully, refresh the device list by clicking `Search` to find the device at its new address.

## Build

Please refer to the [build instructions](https://github.com/EPC-MSU/revealer/blob/dev-2.0/BUILD.md) to build `revealer` from source for your operating system.

## Notes

* A server with support for changing settings via extended SSDP can be found at https://github.com/EPC-MSU/pyssdp_server .

* Discovered devices are sorted first by whether they support settings changes via extended SSDP (those that do appear higher), and then alphabetically within each of the two groups.

* Note that discovering devices on a different subnet may require disabling the firewall — your PC may prompt you to do so on the first launch of `revealer`. Otherwise, you may need to disable the firewall manually.

* For `revealer` to work correctly inside a virtual machine, set the network connection type to "Bridged Adapter" (Network → Adapter 1 → Attached to).

---

# revealer

Программа для поиска сетевых устройств в локальной сети по SSDP / UPnP.

## Поддержка

Windows, Linux, macOS.

## Запуск и использование

1. Выберите приложение для вашей операционной системы и запустите его.
2. Нажмите кнопку `Search`, чтобы получить / обновить список найденных сетевых устройств, поддерживающих SSDP.

    ![image](https://raw.githubusercontent.com/EPC-MSU/revealer/dev-2.0/documentation/images/search.png)
3. В полученном списке доступные устройства, находящиеся в той же локальной сети, что и Ваш компьютер, будут иметь в графе `URL / IP` выделенную кликабельную ссылку (синего цвета с подчеркиванием). Эти страницы могут быть открыты кликом левой кнопкой мыши по соответствующей ячейке столбца `URL / IP`.

    ![image](https://raw.githubusercontent.com/EPC-MSU/revealer/dev-2.0/documentation/images/ready_list.png)
4. Справа от ссылок в соответствующей строке будет иконка информации об устройстве (![image](https://raw.githubusercontent.com/EPC-MSU/revealer/dev-2.0/resources/properties.png)) - при нажатии на неё можно открыть список свойств данного устройства.

    ![image](https://raw.githubusercontent.com/EPC-MSU/revealer/dev-2.0/documentation/images/device_info.png)
5. Для недоступных для Вашего компьютера устройств (в другой подсети) в графе `URL / IP` будет указан только их IP-адрес в другой сети и список информации об устройстве будет короче, поскольку `revealer` не может получить полное описание устройства с помощью HTTP-запроса по ссылке `Location`.

    ![image](https://raw.githubusercontent.com/EPC-MSU/revealer/dev-2.0/documentation/images/device_info_not_local.png)
6. Для устройств, которые поддерживают это расширение протокола, доступна опция изменения IP-адреса с использованием расширенного SSDP. Для этого:
    * С помощью нажатия на иконку с двумя шестеренками (![image](https://raw.githubusercontent.com/EPC-MSU/revealer/dev-2.0/resources/settings2.png)) откройте окно `Change settings...`. Если данная опция недоступна, значит, версия устройства её не поддерживает.
    
        ![image](https://raw.githubusercontent.com/EPC-MSU/revealer/dev-2.0/documentation/images/device_change_settings.png)
    * в открывшимся окне введите пароль устройства, выберете или уберите галочку с DHCP (динамический способ получения сетевых настроек от DHCP-сервера в сети), укажите желаемый IP-адрес, маску подсети и при необходимости шлюз по умолчанию.
    * нажмите `Ок`.
    * через некоторое время появится окно с результатом выполнения установки настроек: если пароль и настройки были приняты устройством для применения, то результат будет `Success` - если же что-то пошло не так, то появится окно `Error`.
    * в случае успешной отправки настроек обновите список устройств кнопкой `Search`, чтобы найти данное устройство с новым адресом.
    
## Сборка

Пожалуйста, воспользуйтесь [инструкцией по сборке](https://github.com/EPC-MSU/revealer/blob/dev-2.0/BUILD.md), чтобы собрать `revelear` из исходного кода для вашей операционной системы.
    
## Замечания

* Сервер с поддержкой изменения настроек по расширенному SSDP можно найти в репозитории https://github.com/EPC-MSU/pyssdp_server .

* Найденные устройства сортируются сначала по принципу "поддерживающие изменение настроек через расширенный SSDP - выше; неподдерживающие - ниже", а затем в каждой из двух этих групп идет сортировка устройств по алфавиту.

* Обратите внимание, что для поиска устройств в другой сети может потребоваться отключение брандмауэра, о чем ваш ПК может попросить при первом старте `revealer`. В ином случае может потребоваться ручное отключение брандмауэра.

* Для корректной работы программы `revealer` на виртуальной машине нужно указать в её настройках тип подключения "Сетевой мост" (Сеть->Адаптер 1->Тип подключения).