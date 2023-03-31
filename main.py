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

from version import Version


class Revealer2:
    SSDP_HEADER_HTTP = "http"
    SSDP_HEADER_SERVER = "server"
    SSDP_HEADER_LOCATION = "location"
    SSDP_HEADER_USN = "usn"

    DEVICE_TYPE_OUR = 0
    DEVICE_TYPE_OTHER = 1

    # To add support of our new device add it in ths dictionary
    #
    # Format: "Name of its SSDP-server": "version of the firmware from which setting IP via multicast is supported"
    # If this device is not supporting setting IP address via multicast yet just leave this string blank and put "".
    #
    # Take note that "Name of its SSDP-server" must be equal to the name in the SERVER string which this device is
    # sending to the SSDP M_SEARCH.
    OUR_DEVICE_DICT = {"8SMC5-USB": "4.7.8", "Eth232-4P": "1.0.13", "mDrive": ""}

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
        mainframe.grid_rowconfigure(2, weight=1)
        mainframe.grid_columnconfigure(0, weight=1)

        mainframe.pack(fill='both', expand="yes")

        # add Search-button
        self.button = ttk.Button(mainframe, text="Search", command=self.ssdp_search)
        self.button.grid(column=0, row=0, sticky='new')

        self.root.bind("<Return>", self.ssdp_search)

        self.our_tree = self.create_tree(mainframe, col=0, row=1, title="Our devices", height=10)
        self.else_tree = self.create_tree(mainframe, col=0, row=2, title="Other devices", height=5)

        for child in mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        # store event for using in clicking callbacks
        self.event = None

    def create_tree(self, master, col, row, title, height):
        """
        Create new Treeview object with our structure.
        :param master: tkinter object
              Parent object in which we should put our new tree.
        :param col: int
              Number of column of the master to put our new tree to.
        :param row: int
              Number of row of the master to put our new tree to.
        :param title: string
              Name of this treeview.
        :return: new_tree: ttk.Treeview object
        """
        # try with frame for title and tree together
        frame = ttk.Frame(master)
        frame.grid(column=col, row=row, sticky='nsew')
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        # label
        label = ttk.Label(frame, text=title, justify=LEFT,
              font=('TkTextFont', font.nametofont('TkTextFont').actual()['size'], 'bold'))
        label.grid(column=0, row=0, sticky=W)

        new_tree = ttk.Treeview(frame, height=height)
        new_tree.grid(column=0, row=1, sticky='nsew')

        # Define the columns
        new_tree['columns'] = ("#", "Device", "URL", "UUID", "Properties")
        new_tree.column("#0", anchor=W, width=0, minwidth=20, stretch=NO)
        new_tree.column("#", anchor=CENTER, width=30, minwidth=30, stretch=NO)
        new_tree.column("Device", anchor=W, width=400, minwidth=150)
        new_tree.column("URL", anchor=W, minwidth=250)
        new_tree.column("UUID", anchor=W, width=0)
        new_tree.column("Properties", anchor=W, width=0)

        # Create Headings
        new_tree.heading("#0", text="", anchor=W)
        new_tree.heading("#", text="#", anchor=CENTER)
        new_tree.heading("URL", text="URL", anchor=CENTER)
        new_tree.heading("Device", text="Device", anchor=CENTER)
        new_tree.heading("UUID", text="UUID", anchor=CENTER)
        new_tree.heading("Properties", text="Properties", anchor=CENTER)

        # make some of the columns visible
        new_tree["displaycolumns"] = ("#", "Device", "URL")

        new_tree.tag_configure("local",
                                    font=font.Font(size=font.nametofont('TkTextFont').actual()['size'],
                                                   weight='bold'))
        new_tree.tag_configure("old_local",
                                    font=font.Font(size=font.nametofont('TkTextFont').actual()['size'],
                                                   weight='bold'))

        # bind double left click and right click
        # bind left-click to 'open_link'
        new_tree.bind("<Double-Button-1>", self.open_link)

        # bind right-click to 'change_ip'
        new_tree.bind("<Button-3>", self.do_popup)

        return new_tree

    def do_popup(self, event):
        self.event = event
        tree = self.event.widget  # get the treeview widget
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

    def view_prop(self):
        tree = self.event.widget  # get the treeview widget
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
                    name = prop_dict = tree.item(iid)['values'][1]
                    print('No properties for this device')

        pass

    def open_link(self, event=None):
        if event is not None:
            self.event = event
        tree = self.event.widget  # get the treeview widget
        try:
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

        except AttributeError:
            pass

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
        for i in self.our_tree.get_children():
            self.our_tree.delete(i)

        self.our_tree.update()

        # remove everything from tree of other devices
        for i in self.else_tree.get_children():
            self.else_tree.delete(i)

        self.else_tree.update()

        self.button["state"] = "disabled"
        self.button["text"] = "Searching..."
        self.button.update()

        devices = set()

        adapters = ifaddr.get_adapters()

        index = [1, 1]
        device_number = [1, 1]

        for adapter in adapters:
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
                            tree_in_use = self.else_tree
                            version_with_settings = ""
                            type_device = 1

                            try:
                                version_with_settings = Revealer2.OUR_DEVICE_DICT[data_dict["server"]]
                                tree_in_use = self.our_tree
                                type_device = Revealer2.DEVICE_TYPE_OUR
                            except KeyError:
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

                                tree_in_use.insert(parent='', index=str(device_number[type_device]), iid=index[type_device], text="",
                                                   values=(str(device_number[type_device]), xml_dict["friendlyName"],
                                                   link, "", xml_dict))

                                tree_in_use.item(index[type_device], tags="local")

                                index[type_device] += 1
                            else:
                                uuid = data_dict["uuid"]

                                # we need to check that if we have our device it supports setting settings via multicast
                                if version_with_settings != "":
                                    version_with_settings_array = [int(num) for num in version_with_settings.split('.')]
                                    current_version = data_dict["version"].split('.')
                                    current_version_array = [int(num) for num in current_version]
                                    print(version_with_settings_array, current_version_array)

                                    # check that we have version greater than this
                                    if current_version_array[0] < version_with_settings_array[0]:
                                        uuid = ""
                                    elif current_version_array[1] < version_with_settings_array[1]:
                                        uuid = ""
                                    elif current_version_array[2] < version_with_settings_array[2]:
                                        uuid = ""

                                    print(uuid)

                                tree_in_use.insert(parent='', index=str(device_number[type_device]), iid=index[type_device], text="",
                                                   values=(str(device_number[type_device]), data_dict["server"], data_dict["ssdp_url"],
                                                   uuid, data_dict))
                                tree_in_use.item(index[type_device], tags="not_local")
                                index[type_device] += 1

                            # update this tree to view new device
                            tree_in_use.update()

                            device_number[type_device] += 1

                except socket.timeout:
                    sock.close()
                    # pass
                    old_devices = self.old_search(devices, device_number[Revealer2.DEVICE_TYPE_OUR],
                                                  index[Revealer2.DEVICE_TYPE_OUR], ip.ip)
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
                    if words_string[1][0] != ' ':  # we should check if we have ' ' here and not take it to the location string
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

        except urllib.error.URLError:
            # print('can\'t open')
            return None

    def change_ip_multicast(self, iid, uuid, new_ip, net_mask='255.255.240.0'):
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
            mb.showinfo(
                "Change settings...",
                "Success.\nNew settings were applied.\nPlease update list of the devices to find this device with the new IP address.",
                parent=self.root
            )
            self.our_tree.delete(iid)
            self.our_tree.update()
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

    def old_search(self, ssdp_devices, device_number, index, ip):
        """
        Perform old version of searching devices in the local network as in the revealer 0.1.0
        Sends multicast packet with special string and listen for the answers.
        :return:
        """

        ssdp_device_number = device_number
        ssdp_index = index

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

                    #title = self.get_page_title("http://" + addr[0] + ":8080")

                    title = "Device undefined (legacy protocol)"

                    self.our_tree.insert(parent='', index=str(ssdp_device_number), iid=ssdp_index, text="",
                                         values=(str(ssdp_device_number), title,
                                                 "http://" + addr[0] + ":8080", ''))
                    self.our_tree.item(ssdp_index, tags="old_local")

                    self.our_tree.update()
                    ssdp_index += 1
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
                    Label(master, text=label_name + ": ", justify=LEFT, font=('TkTextFont', font.nametofont('TkTextFont').actual()['size'], 'bold')).grid(column=0, row=row_index, padx=5, sticky=W)
                    if name == 'presentationURL':
                        Label(master, text=self.url, justify=LEFT, cursor='hand2', font=('TkTextFont', font.nametofont('TkTextFont').actual()['size'], 'underline')).grid(column=1, row=row_index, padx=5, sticky=W)
                    else:
                        if self.dict[name][0:4] == "http":
                            font_style = 'underline'
                            cursor = 'hand2'
                        Label(master, text=self.dict[name], justify=LEFT, cursor=cursor, font=('TkTextFont', font.nametofont('TkTextFont').actual()['size'], font_style)).grid(column=1, row=row_index, padx=5, sticky=W)
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
