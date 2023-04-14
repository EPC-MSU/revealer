from tkinter import *
from tkinter import ttk, font
import tkinter.messagebox as mb
import tkinter.simpledialog as sd

import socket
import ifaddr
import webbrowser as wb

import xml.etree.ElementTree as ET
import urllib.request

import ast
import threading

from version import Version


class SSDPEnhancedDevice:
    def __init__(self, ssdp_device_name, enhanced_ssdp_support_min_fw, enhanced_ssdp_version):
        self.ssdp_device_name = ssdp_device_name
        self.enhanced_ssdp_support_min_fw = enhanced_ssdp_support_min_fw
        self.enhanced_ssdp_version = enhanced_ssdp_version


class Revealer2:
    SSDP_HEADER_HTTP = "http"
    SSDP_HEADER_SERVER = "server"
    SSDP_HEADER_LOCATION = "location"
    SSDP_HEADER_USN = "usn"

    DEVICE_TYPE_OUR = 0
    DEVICE_TYPE_OTHER = 1

    EVEN_ROW_COLOR = "#f3f6f6"

    # To add support of our new device add it in ths dictionary
    #
    # Format: "Name of its SSDP-server": "version of the firmware from which setting IP via multicast is supported"
    # If this device is not supporting setting IP address via multicast yet just leave this string blank and put "".
    #
    # Take note that "Name of its SSDP-server" must be equal to the name in the SERVER string which this device is
    # sending to the SSDP M_SEARCH.
    # OUR_DEVICE_DICT = {"8SMC5-USB": "4.7.8", "Eth232-4P": "1.0.13", "mDrive": ""}

    SSDP_ENHANCED_DEVICES = [
        SSDPEnhancedDevice(
            ssdp_device_name="8SMC5-USB",
            enhanced_ssdp_support_min_fw="4.7.8",
            enhanced_ssdp_version="1.0.0"
        ),
        SSDPEnhancedDevice(
            ssdp_device_name="Eth232-4P",
            enhanced_ssdp_support_min_fw="1.0.13",
            enhanced_ssdp_version="1.0.0"
        ),
        SSDPEnhancedDevice(
            ssdp_device_name="mDrive",
            enhanced_ssdp_support_min_fw="4.7.8",
            enhanced_ssdp_version="1.0.0"
        )
    ]

    def __init__(self):

        self.root = Tk()
        self.root.title("Revealer " + Version.full)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # add revealer icon
        try:
            self.root.iconphoto(False, PhotoImage(file="resources/appicon.png"))
        except:
            pass

        mainframe = ttk.Frame(self.root, padding="8 3 8 8")
        mainframe.grid(column=0, row=0, sticky=(N, W, E, S))

        mainframe.grid_rowconfigure(1, weight=1)
        # mainframe.grid_rowconfigure(2, weight=1)
        mainframe.grid_columnconfigure(0, weight=1)

        mainframe.pack(fill='both', expand="yes")

        # add Search-button
        self.button = ttk.Button(mainframe, text="Search", command=self.start_thread_search)
        self.button.grid(column=0, row=0, sticky='new')

        self.root.bind("<Return>", self.ssdp_search)

        self.main_table = self.create_table(mainframe, col=0, row=1, height=300)

        for child in mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        # store event for using in clicking callbacks
        self.event = None

    def start_thread_search(self):
        search_thread = threading.Thread(target=self.ssdp_search)
        search_thread.start()

    def create_table(self, master, col, row, height):
        # try with frame for title and tree together
        frame = Frame(master, borderwidth=1, relief="solid", background='white', height=height, width=500)
        frame.grid(column=col, row=row, sticky='nsew')
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        frame.grid_propagate(False)

        header_color = "#dee0e0"

        new_table = Frame(frame, background=header_color)
        new_table.grid(column=0, row=0, sticky='nsew')

        #scrollbar = Scrollbar(frame, orient="vertical")
        #scrollbar.grid(column=1, row=0, sticky='ns')

        # Label(new_table, text="#", anchor="w", width=0).grid(row=0, column=0, sticky="ew")
        header_1 = Label(new_table, text="Device", anchor="center", background=header_color)
        header_1.grid(row=0, column=0, sticky="ew")
        header_1.header = "yes"

        header_2 = ttk.Separator(new_table, takefocus=0, orient=VERTICAL)
        header_2.grid(row=0, column=1, sticky="ns")
        header_2.header = "yes"

        header_3 = Label(new_table, text="URL", anchor="center", background=header_color, height=0)
        header_3.grid(row=0, column=2, sticky="ew")
        header_3.header = "yes"

        print(header_3['height'])

        new_table.grid_columnconfigure(0, weight=1, minsize=100)
        new_table.grid_columnconfigure(1, weight=0)
        new_table.grid_columnconfigure(2, weight=1, minsize=100)

        # bind double left click and right click
        # bind left-click to 'open_link'
        new_table.bind("<Button-1>", self.open_link)

        # bind right-click to 'change_ip'
        new_table.bind("<Button-3>", self.do_popup)

        return new_table

    def find_ssdp_enhanced_device(self, device_name):
        index = 0

        while index < len(self.SSDP_ENHANCED_DEVICES):
            if self.SSDP_ENHANCED_DEVICES[index].ssdp_device_name.lower() == device_name.lower():
                return index

            index += 1

        return None

    def do_popup(self, event):
        self.event = event
        tree = self.event.widget  # get the treeview widget
        if tree.winfo_class() == 'Treeview':
            region = tree.identify_region(self.event.x, self.event.y)
            iid = tree.identify('item', self.event.x, self.event.y)
            tags = tree.item(iid)['tags'][0]
            uuid = tree.item(iid)['values'][3]

            # test
            menu = Menu(self.root, tearoff=0)

            if region == 'cell':
                try:
                    if tags == "local":
                        menu.add_command(label="Open web-page", command=self.open_link)
                        menu.add_separator()
                        menu.add_command(label="Properties", command=self.view_prop)
                        menu.tk_popup(event.x_root, event.y_root)
                    elif tags == "not_local" and uuid != "":
                        menu.delete(0, 2)
                        menu.add_command(label="Change settings...", command=self.change_ip_click)
                        menu.add_separator()
                        menu.add_command(label="Properties", command=self.view_prop)
                        menu.tk_popup(event.x_root, event.y_root)
                    elif tags == "not_local":
                        menu.delete(0, 2)
                        menu.add_command(label="Change settings...", command=self.change_ip_click)
                        menu.entryconfig(1, state=DISABLED)
                        menu.add_separator()
                        menu.add_command(label="Properties", command=self.view_prop)
                        menu.tk_popup(event.x_root, event.y_root)
                    elif tags == "old_local":
                        menu.delete(0, 2)
                        menu.add_command(label="Open web-page", command=self.open_link)
                        menu.add_separator()
                        menu.add_command(label="Properties", command=self.view_prop)
                        menu.entryconfig(2, state=DISABLED)
                        menu.tk_popup(event.x_root, event.y_root)

                finally:
                    menu.grab_release()

        if tree.winfo_class() == 'Label':
            menu = Menu(self.root, tearoff=0)

            try:
                tags = tree.tag
                if tags == "local":
                    menu.add_command(label="Open web-page", command=self.open_link)
                    menu.add_separator()
                    menu.add_command(label="Properties", command=self.view_prop)
                    menu.tk_popup(event.x_root, event.y_root)
                elif tags == "not_local":  # and uuid != "":
                    menu.delete(0, 2)
                    menu.add_command(label="Change settings...", command=self.change_ip_click)
                    menu.add_separator()
                    menu.add_command(label="Properties", command=self.view_prop)
                    menu.tk_popup(event.x_root, event.y_root)
                elif tags == "not_local":
                    menu.delete(0, 2)
                    menu.add_command(label="Change settings...", command=self.change_ip_click)
                    menu.entryconfig(1, state=DISABLED)
                    menu.add_separator()
                    menu.add_command(label="Properties", command=self.view_prop)
                    menu.tk_popup(event.x_root, event.y_root)
                elif tags == "old_local":
                    menu.delete(0, 2)
                    menu.add_command(label="Open web-page", command=self.open_link)
                    menu.add_separator()
                    menu.add_command(label="Properties", command=self.view_prop)
                    menu.entryconfig(2, state=DISABLED)
                    menu.tk_popup(event.x_root, event.y_root)

            finally:
                menu.grab_release()

    def view_prop(self):
        tree = self.event.widget  # get the treeview widget

        if tree.winfo_class() == "Treeview":
            region = tree.identify_region(self.event.x, self.event.y)
            col = tree.identify_column(self.event.x)
            iid = tree.identify('item', self.event.x, self.event.y)

            name = ''
            if region == 'cell':
                prop_dict = ast.literal_eval(tree.item(iid)['values'][4])
                try:
                    # if we have local SSDP device
                    name = prop_dict['friendlyName']
                    PropDialog(name, prop_dict, tree.item(iid)['values'][2], parent=self.root)
                except KeyError:
                    try:
                        # if we have not local SSDP device
                        name = prop_dict['server']
                        PropDialog(name, prop_dict, tree.item(iid)['values'][2], parent=self.root)
                    except KeyError:
                        prop_dict = tree.item(iid)['values'][1]
                        print('No properties for this device')
                        pass
        elif tree.winfo_class() == "Label":
            if hasattr(tree, "other_data") and hasattr(tree, "link"):
                prop_dict = tree.other_data
                try:
                    # if we have local SSDP device
                    name = prop_dict['friendlyName']
                    PropDialog(name, prop_dict, tree.link, parent=self.root)
                except KeyError:
                    try:
                        # if we have not local SSDP device
                        name = prop_dict['server']
                        PropDialog(name, prop_dict, tree.link, parent=self.root)
                    except KeyError:
                        print('No properties for this device')
                        pass

    def open_link(self, event=None):
        if event is not None:
            self.event = event
        tree = self.event.widget  # get the treeview widget
        if tree.winfo_class() == 'Treeview':
            region = tree.identify_region(self.event.x, self.event.y)
            col = tree.identify_column(self.event.x)
            iid = tree.identify('item', self.event.x, self.event.y)
            link = tree.item(iid)['values'][2]  # get the link from the selected row
            tags = tree.item(iid)['tags'][0]

            if event is not None:
                if region == 'cell' and col == '#3':
                    if tags == "local" or tags == "old_local":
                        wb.open_new_tab(link)  # open the link in a browser tab
                    else:
                        print("Can't open this link.")
            else:
                if region == 'cell':
                    if tags == "local" or tags == "old_local":
                        wb.open_new_tab(link)  # open the link in a browser tab
                    else:
                        print("Can't open this link.")

        if tree.winfo_class() == 'Label':
            if hasattr(tree, 'link') and hasattr(tree, 'tag'):
                if tree.tag == "local" or tree.tag == "old_local":
                    wb.open_new_tab(tree.link)  # open the link in a browser tab
                else:
                    print("Can't open this link.")

    def add_row_item(self, row, name, link, uuid, other_data, tag):

        if row % 2 == 0:
            bg_color = self.EVEN_ROW_COLOR
        else:
            bg_color = "white"

        Label(self.main_table, text="", anchor="w", background=bg_color).grid(row=row, column=1, sticky="ns")

        if tag != "not_local":
            device = Label(self.main_table, text=name, anchor="w", background=bg_color, font=('TkTextFont', font.nametofont('TkTextFont').actual()['size'], 'bold'))
            link = Label(self.main_table, text=link, anchor="w", background=bg_color, cursor='hand2', fg="blue",
                         font=('TkTextFont', font.nametofont('TkTextFont').actual()['size'], 'underline'))
        else:
            device = Label(self.main_table, text=name, anchor="w", background=bg_color)
            link = Label(self.main_table, text=link, anchor="w", background=bg_color,
                         font=('TkTextFont', font.nametofont('TkTextFont').actual()['size'], ''))

        link.grid(row=row, column=2, sticky="ew")
        device.grid(row=row, column=0, sticky="ew")

        device.tag = tag
        link.tag = tag

        device.link = link['text']
        link.link = link['text']

        device.uuid = uuid
        device.other_data = other_data

        link.uuid = uuid
        link.other_data = other_data

        # bind double left click and right click
        # bind left-click to 'open_link'
        link.bind("<Button-1>", self.open_link)

        # bind right-click to 'change_ip'
        link.bind("<Button-3>", self.do_popup)
        device.bind("<Button-3>", self.do_popup)

        return

    def move_table_rows(self, row_start, direction='down'):
        """
        Function moves every row of the main table to the next one since we need to sort our devices in the list.
        :param row_start: int
           First row to move.
        :param direction: str
           Direction of the movement of the rows. Can be 'up' or 'down'.
        :return:
        """

        additional_row = 1

        if direction == 'down':
            additional_row = 1
        elif direction == 'up':
            additional_row = -1

        for widget in self.main_table.winfo_children():
            row = widget.grid_info()['row']
            col = widget.grid_info()['column']
            if row >= row_start:
                widget.grid(column=col, row=row+additional_row)
                if (row+additional_row) % 2 == 0:
                    widget["background"] = self.EVEN_ROW_COLOR
                else:
                    widget["background"] = "white"

    def delete_table_row(self, del_row):
        for widget in self.main_table.winfo_children():
            row = widget.grid_info()['row']
            col = widget.grid_info()['column']
            if row == del_row:
                print(widget['text'], row, "DELETE")
                widget.destroy()

        self.move_table_rows(del_row+1, direction='up')

    def ssdp_search(self):
        # M-Search message body
        message = \
            'M-SEARCH * HTTP/1.1\r\n' \
            'HOST:239.255.255.250:1900\r\n' \
            'ST:upnp:rootdevice\r\n' \
            'MX:1\r\n' \
            'MAN:"ssdp:discover"\r\n' \
            '\r\n'

        # remove everything from our tree
        """for i in self.our_tree.get_children():
            self.our_tree.delete(i)

        self.our_tree.update()"""

        for i in self.main_table.winfo_children():
            if not hasattr(i, "header"):
                i.destroy()

        # remove everything from tree of other devices
        # for i in self.else_tree.get_children():
        #   self.else_tree.delete(i)

        # self.else_tree.update()

        self.button["state"] = "disabled"
        self.button["text"] = "Searching..."
        self.button.update()

        devices = set()

        adapters = ifaddr.get_adapters()

        device_number = [0, 0]

        for adapter in adapters:
            for ip in adapter.ips:
                if not isinstance(ip.ip, str):
                    continue

                if ip.ip == '127.0.0.1':
                    continue

                # print(ip.ip)

                # Send M-Search message to multicast address for UPNP
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                try:
                    sock.bind((ip.ip, 0))
                except:
                    # print('   Can\'t bind to this ip')
                    continue

                # set timeout
                sock.settimeout(1)
                try:
                    sock.sendto(message.encode('utf-8'), ("239.255.255.250", 1900))
                except OSError as err:
                    print(err)
                    continue

                # listen and capture returned responses
                try:
                    while True:
                        data, addr = sock.recvfrom(8192)
                        data_dict = self.parse_ssdp_data(data.decode('utf-8'))

                        # if we have not received this location before
                        if not data_dict["ssdp_url"] in devices:
                            devices.add(data_dict["ssdp_url"])

                            xml_dict = self.parse_upnp_xml(data_dict["location"])

                            # check is this our device or not
                            version_with_settings = ""
                            type_device = Revealer2.DEVICE_TYPE_OUR
                            other_type = Revealer2.DEVICE_TYPE_OTHER

                            device_index_in_list = self.find_ssdp_enhanced_device(data_dict["server"])

                            if device_index_in_list is not None:
                                version_with_settings = self.SSDP_ENHANCED_DEVICES[device_index_in_list].enhanced_ssdp_support_min_fw
                                type_device = Revealer2.DEVICE_TYPE_OUR
                                device_number[Revealer2.DEVICE_TYPE_OTHER] += 1
                            else:
                                version_with_settings = ""
                                type_device = Revealer2.DEVICE_TYPE_OTHER
                                pass

                            if xml_dict is not None:
                                link = ""

                                # check that we have our url with correct format
                                if xml_dict["presentationURL"][0:4] != "http":
                                    link = "http://" + addr[0] + xml_dict["presentationURL"]
                                else:
                                    link = xml_dict["presentationURL"]

                                xml_dict["version"] = data_dict["version"]

                                self.add_row_item(device_number[type_device] + 1, xml_dict["friendlyName"],
                                                  link, "", xml_dict, tag="local")
                            else:
                                uuid = data_dict["uuid"]

                                # we need to check that if we have our device it supports setting settings via multicast
                                if version_with_settings != "":
                                    version_with_settings_array = [int(num) for num in version_with_settings.split('.')]
                                    current_version = data_dict["version"].split('.')
                                    current_version_array = [int(num) for num in current_version]

                                    # check that we have version greater than this
                                    if current_version_array[0] < version_with_settings_array[0]:
                                        uuid = ""
                                    elif current_version_array[1] < version_with_settings_array[1]:
                                        uuid = ""
                                    elif current_version_array[2] < version_with_settings_array[2]:
                                        uuid = ""

                                self.add_row_item(device_number[type_device] + 1, data_dict["server"],
                                                  data_dict["ssdp_url"], uuid, data_dict, tag="not_local")

                            device_number[type_device] += 1

                except socket.timeout:
                    sock.close()
                    # pass
                    old_devices = self.old_search(devices, device_number[Revealer2.DEVICE_TYPE_OUR], ip.ip)
                    for device in old_devices:
                        devices.add(device)

        self.button["state"] = "normal"
        self.button["text"] = "Search"
        self.button.update()

        return

    @staticmethod
    def parse_ssdp_data(ssdp_data):
        ssdp_dict = {"server": "", "version": "", "location": "", "ssdp_url": "", "uuid": ""}
        ssdp_strings = ssdp_data.split("\r\n")

        for string in ssdp_strings:
            if string[0:3].lower() != Revealer2.SSDP_HEADER_HTTP:
                words_string = string.split(':')

                if words_string[
                    0].lower() == Revealer2.SSDP_HEADER_SERVER:  # format: SERVER: lwIP/1.4.1 UPnP/2.0 8SMC5-USB/4.7.7
                    words_string = string.split(' ')
                    server_version = words_string[len(words_string) - 1]  # last word after ' '
                    server_version_words = server_version.split('/')
                    # TODO: we need try/except here
                    ssdp_dict["server"] = server_version_words[0]
                    try:
                        ssdp_dict["version"] = server_version_words[1]
                    except IndexError:
                        ssdp_dict["version"] = '-'

                elif words_string[
                    0].lower() == Revealer2.SSDP_HEADER_LOCATION:  # format: LOCATION: http://172.16.130.67:80/Basic_info.xml
                    words_string = string.split(':')  # do this again for symmetry
                    if words_string[1][
                        0] != ' ':  # we should check if we have ' ' here and not take it to the location string
                        ssdp_dict["location"] = words_string[1] + ':' + words_string[2] + ':' + words_string[3]
                    else:
                        ssdp_dict["location"] = words_string[1][1::1] + ':' + words_string[2] + ':' + words_string[3]

                    ssdp_dict["ssdp_url"] = words_string[2][2::1]  # save only IP  addr

                elif words_string[
                    0].lower() == Revealer2.SSDP_HEADER_USN:  # format: USN: uuid:40001d0a-0000-0000-8e31-4010900b00c8::upnp:rootdevice
                    words_string = string.split(':')  # do this again for symmetry
                    ssdp_dict["uuid"] = words_string[2]

        return ssdp_dict

    @staticmethod
    def parse_upnp_xml(url):
        xml_dict = {}

        try:
            response = urllib.request.urlopen(url, timeout=0.1).read().decode('utf-8')
            data = response.split('\r\n\r\n')  # we need to get rid of the headers

            tree = ET.fromstring(data[len(data) - 1])

            for child in tree:
                tag_array = child.tag.split('}')
                tag_name = tag_array[len(tag_array) - 1]
                xml_dict[tag_name] = child.text

                for grandchild in child:
                    tag_array = grandchild.tag.split('}')
                    tag_name = tag_array[len(tag_array) - 1]
                    xml_dict[tag_name] = grandchild.text

                    # print(f'Tag: {grandchild.tag}, text: {grandchild.text}')
            return xml_dict

        except:
            # print('can\'t open')
            return None

    def change_ip_multicast(self, row, uuid, new_ip, net_mask='255.255.0.0'):
        """
        Function for changing device's net settings (IP address and network mask) via multicast. We are using same
        protocol as for SSDP M-SEARCH but setting its aim as desired device's UUID and add new header in format:

            MIPAS: 198.16.1.1;255.255.240.0;\r\n

        (MIPAS - Multicast IP Address Setting)

        :param uuid: string
            UUID of the device net settings of which should be modified.
        :param new_ip: string
            New IP address for this device
        :param net_mask: string

        :return:
        """

        # M-Search message body for changing IP address of this current device
        message = \
            'M-SEARCH * HTTP/1.1\r\n' \
            'HOST:239.255.255.250:1900\r\n' \
            'ST:uuid:' + uuid + '\r\n' \
                                'MX:2\r\n' \
                                'MAN:"ssdp:discover"\r\n' \
                                'MIPAS:' + new_ip + ';' + net_mask + ';\r\n' \
                                                                     '\r\n'

        self.button["state"] = "disabled"
        self.button["text"] = "Search"
        self.button.update()

        devices = set()

        adapters = ifaddr.get_adapters()

        for adapter in adapters:
            if len(devices) > 0:
                break
            for ip in adapter.ips:
                if not isinstance(ip.ip, str):
                    continue

                if ip.ip == '127.0.0.1':
                    continue

                # Send M-Search message to multicast address for UPNP
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                try:
                    sock.bind((ip.ip, 0))
                except:
                    # print('   Can\'t bind to this ip')
                    continue

                sock.settimeout(1)
                try:
                    sock.sendto(message.encode('utf-8'), ("239.255.255.250", 1900))
                except OSError as err:
                    print(err)
                    continue

                # listen and capture returned responses
                try:
                    while True:
                        data, addr = sock.recvfrom(8192)
                        data_dict = self.parse_ssdp_data(data.decode('utf-8'))

                        # if we have not received this location before
                        if not data_dict["location"] in devices:
                            devices.add(data_dict["location"])

                except socket.timeout:
                    sock.close()
                    if len(devices) > 0:
                        break
                    pass

        # if we received an answer - we have not broken the device (at least)
        # so delete it from the list
        if len(devices) > 0:
            self.delete_table_row(row)

            mb.showinfo(
                "Change settings...",
                "Success.\nNew settings were applied.\nPlease update list of the devices to find this device with the new IP address.",
                parent=self.root
            )

        else:
            mb.showerror(
                "Change settings...",
                "Error.\nSomething went wrong while setting new settings.\nPlease check inserted values and try again.",
                parent=self.root
            )

        # TODO: we should check if we have changed the device's settings or not
        # TODO: problem is that maybe we shouldn't response with some new data you know

        self.button["state"] = "normal"
        self.button["text"] = "Search"
        self.button.update()

    def change_ip_click(self):
        tree = self.event.widget  # get the treeview widget

        if tree.winfo_class() == "Treeview":
            region = tree.identify_region(self.event.x, self.event.y)
            col = tree.identify_column(self.event.x)
            iid = tree.identify('item', self.event.x, self.event.y)
            if region == 'cell':
                device = tree.item(iid)['values'][1]  # get the link from the selected row
                uuid = tree.item(iid)['values'][3]
                tags = tree.item(iid)['tags'][0]
                if tags != "local":
                    # print(tree.item(iid)['values'][3])
                    # test window
                    dialog = MIPASDialog("Change settings...", device, uuid, parent=self.root)
                    if dialog.result is not None:
                        try:
                            ip, net_mask = dialog.result
                            print(ip, net_mask)

                            # request changing net settings
                            self.change_ip_multicast(iid, uuid, ip, net_mask)
                        except ValueError as err:
                            print(f"In values there were some error: {dialog.result}")

        elif tree.winfo_class() == "Label":
            if hasattr(tree, "link") and hasattr(tree, "tag") and hasattr(tree, "uuid"):
                if tree.tag == "not_local":
                    dialog = MIPASDialog("Change settings...", tree.other_data["server"], tree.uuid, parent=self.root)
                    if dialog.result is not None:
                        try:
                            ip, net_mask = dialog.result
                            print(ip, net_mask)

                            # request changing net settings
                            self.change_ip_multicast(tree.grid_info()["row"], tree.uuid, ip, net_mask)
                        except ValueError as err:
                            print(f"In values there were some error: {dialog.result}")

    @staticmethod
    def get_page_title(url):
        title = ""
        try:
            response = urllib.request.urlopen(url, timeout=0.3).read().decode('utf-8')

            # data = response.split('title>')  # we need to get rid of the headers
            title = response[response.find('<title>') + 7: response.find('</title>')]
            # print(title)

            return title

        except urllib.error.URLError:
            # print('can\'t open')
            return title

    def old_search(self, ssdp_devices, device_number, ip):
        """
        Perform old version of searching devices in the local network as in the revealer 0.1.0
        Sends multicast packet with special string and listen for the answers.
        :return:
        """

        ssdp_device_number = device_number

        devices = set()

        # Send M-Search message to multicast address for UPNP
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.bind((ip, 0))
        except:
            # print('   Can\'t bind to this ip')
            return devices

        try:
            message = "DISCOVER_CUBIELORD_REQUEST " + str(sock.getsockname()[1])
        except:
            print('error while getting socket port number')
            return devices

        sock.settimeout(0.5)
        try:
            sock.sendto(message.encode('utf-8'), ("255.255.255.255", 8008))
        except OSError as err:
            print(err)
            return devices

        # listen and capture returned responses
        try:
            while True:
                data, addr = sock.recvfrom(8192)
                if addr[0] not in devices and addr[0] not in ssdp_devices:
                    devices.add(addr[0])

                    # title = self.get_page_title("http://" + addr[0] + ":8080")

                    title = "Device undefined (legacy protocol)"

                    self.move_table_rows(ssdp_device_number+1)

                    self.add_row_item(ssdp_device_number + 1, title,
                                      "http://" + addr[0] + ":8080", "", "", tag="old_local")

                    ssdp_device_number += 1

        except socket.timeout:
            sock.close()
            pass

        return devices


class MIPASDialog(sd.Dialog):
    def __init__(self, title, device, uuid,
                 initialvalue=None,
                 minvalue=None, maxvalue=None,
                 parent=None):

        self.device = device
        self.uuid = uuid
        self.minvalue = minvalue
        self.maxvalue = maxvalue

        self.initialvalue = initialvalue

        self.entry_ip = None
        self.entry_mask = None

        sd.Dialog.__init__(self, parent, title)

    def destroy(self):
        self.entry_ip = None
        self.entry_mask = None
        sd.Dialog.destroy(self)

    def body(self, master):

        d_label = Label(master, text="Device: ", justify=LEFT)
        d_label.grid(column=0, row=0, padx=5, sticky=W)

        device = Label(master, text=self.device, justify=LEFT)
        device.grid(column=1, row=0, padx=5, sticky=W)

        u_label = Label(master, text="UUID: ", justify=LEFT)
        u_label.grid(column=0, row=1, padx=5, sticky=W)

        uuid = Label(master, text=self.uuid, justify=LEFT)
        uuid.grid(column=1, row=1, padx=5, sticky=W)

        ip_label = Label(master, text="New IP address: ", justify=LEFT)
        ip_label.grid(column=0, row=2, padx=5, pady=5, sticky=W)

        netmask_label = Label(master, text="New Network Mask: ", justify=LEFT)
        netmask_label.grid(column=0, row=3, padx=5, pady=5, sticky=W)

        self.entry_ip = Entry(master, name="entry_ip")
        self.entry_ip.grid(column=1, row=2, padx=5, pady=5, sticky=W + E)

        if self.initialvalue is not None:
            self.entry_ip.insert(0, self.initialvalue)
            self.entry_ip.select_range(0, END)

        self.entry_mask = Entry(master, name="entry_mask")
        self.entry_mask.grid(column=1, row=3, padx=5, pady=5, sticky=W + E)

        if self.initialvalue is not None:
            self.entry_mask.insert(0, self.initialvalue)
            self.entry_mask.select_range(0, END)

        return self.entry_ip

    def validate(self):
        try:
            result_ip = self.getresult()
        except ValueError:
            mb.showwarning(
                "Illegal value",
                "\nPlease try again",
                parent=self
            )
            return 0

        # TODO: maybe we need to validate here

        self.result = result_ip

        return 1

    def getresult(self):
        return self.entry_ip.get(), self.entry_mask.get()


class PropDialog(sd.Dialog):
    def __init__(self, device_name, properties_dict, URL,
                 parent=None):

        self.name = device_name
        self.url = URL

        self.dict = properties_dict

        self.labels_dict = {'friendlyName': 'Friendly name', 'manufacturer': 'Manufacturer',
                            'manufacturerURL': 'Manufacturer URL', 'modelDescription': 'Model description',
                            'modelName': 'Model name', 'modelNumber': 'Model number', 'modelURL': 'Model URL',
                            'serialNumber': 'Serial number', 'UDN': 'UDN', 'presentationURL': 'Presentation URL',
                            'server': 'SSDP server', 'uuid': 'UUID', 'version': 'Firmware version', 'ssdp_url': 'URL'}

        sd.Dialog.__init__(self, parent, device_name)

    def destroy(self):
        sd.Dialog.destroy(self)

    def body(self, master):

        row_index = 0

        for name in self.dict:
            font_style = ''
            cursor = ''
            if self.dict[name] is not None:
                try:
                    label_name = self.labels_dict[name]
                    Label(master, text=label_name + ": ", justify=LEFT,
                          font=('TkTextFont', font.nametofont('TkTextFont').actual()['size'], 'bold')).grid(column=0,
                                                                                                            row=row_index,
                                                                                                            padx=5,
                                                                                                            sticky=W)
                    if name == 'presentationURL':
                        Label(master, text=self.url, justify=LEFT, cursor='hand2',
                              font=('TkTextFont', font.nametofont('TkTextFont').actual()['size'], 'underline')).grid(
                            column=1, row=row_index, padx=5, sticky=W)
                    else:
                        if self.dict[name][0:4] == "http":
                            font_style = 'underline'
                            cursor = 'hand2'
                        Label(master, text=self.dict[name], justify=LEFT, cursor=cursor,
                              font=('TkTextFont', font.nametofont('TkTextFont').actual()['size'], font_style)).grid(
                            column=1, row=row_index, padx=5, sticky=W)
                    row_index += 1
                except KeyError:
                    pass

        self.bind("<Button-1>", self.open_link)

        return self

    def buttonbox(self):
        '''add standard button box.

        override if you do not want the standard buttons
        '''

        box = Frame(self)

        w = Button(box, text="OK", width=10, command=self.ok, default=ACTIVE)
        w.pack(side=LEFT, padx=5, pady=5)

        self.bind("<Return>", self.ok)

        box.pack()

    def validate(self):
        try:
            result = self.getresult()
        except ValueError:
            mb.showwarning(
                "Illegal value",
                "\nPlease try again",
                parent=self
            )
            return 0

        # TODO: maybe we need to validate here

        self.result = result

        return 1

    def getresult(self):
        return self.name

    def open_link(self, event):
        label = event.widget  # get the label widget
        try:
            link = label['text']

            # if we have link in the label object that we double-clicked -> open it
            if link[0:4] == "http":
                wb.open_new_tab(link)
        except TclError as err:
            print('Tkinter error:', err)


if __name__ == '__main__':
    print("Start Revealer 2... Version " + Version.full + ".")
    app = Revealer2()
    app.root.mainloop()
