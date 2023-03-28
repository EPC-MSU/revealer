from tkinter import *
from tkinter import ttk, font
import tkinter.messagebox as mb
import tkinter.simpledialog as sd

import socket
import ifaddr
import webbrowser as wb

import xml.etree.ElementTree as ET
import urllib.request

import textwrap

from version import Version


def wrap(string, length=8):
    return '\n'.join(textwrap.wrap(string, length))


class MIPASDialog(sd.Dialog):
    def __init__(self, title, device, uuid,
                 initialvalue=None,
                 minvalue=None, maxvalue = None,
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
        self.entry_ip.grid(column=1, row=2, padx=5, pady=5, sticky=W+E)

        if self.initialvalue is not None:
            self.entry_ip.insert(0, self.initialvalue)
            self.entry_ip.select_range(0, END)

        self.entry_mask = Entry(master, name="entry_mask")
        self.entry_mask.grid(column=1, row=3, padx=5, pady=5, sticky=W+E)

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


class Revealer2:

    SSDP_HEADER_HTTP = "http"
    SSDP_HEADER_SERVER = "server"
    SSDP_HEADER_LOCATION = "location"
    SSDP_HEADER_USN = "usn"

    def __init__(self):

        self.root = Tk()
        self.root.title("Revealer 2 " + Version.full)

        self.root.iconphoto(False, PhotoImage(file="resources/appicon.png"))

        mainframe = ttk.Frame(self.root, padding="8 3 8 8")
        mainframe.grid(column=0, row=0, sticky=(N, W, E, S))

        # mainframe.grid_rowconfigure(0, weight=1)
        mainframe.grid_rowconfigure(1, weight=1)
        mainframe.grid_columnconfigure(0, weight=1)

        mainframe.pack(fill='both', expand="yes")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # try with tree
        self.tree = ttk.Treeview(mainframe)
        self.tree.grid(column=0, row=1, sticky='nsew')

        # Define the columns
        self.tree['columns'] = ("#", "Device", "URL", "UUID")
        self.tree.column("#0", anchor=W, width=20, minwidth=20, stretch=NO)
        self.tree.column("#", anchor=CENTER, width=30, minwidth=30, stretch=NO)
        self.tree.column("Device", anchor=W, minwidth=150)
        self.tree.column("URL", anchor=W, minwidth=250)
        self.tree.column("UUID", anchor=W, width=0)

        # Create Headings
        self.tree.heading("#0", text="", anchor=W)
        self.tree.heading("#", text="#", anchor=CENTER)
        self.tree.heading("URL", text="URL", anchor=CENTER)
        self.tree.heading("Device", text="Device", anchor=CENTER)
        self.tree.heading("UUID", text="UUID", anchor=CENTER)

        # make some of the columns visible
        self.tree["displaycolumns"] = ("#", "Device", "URL")

        self.button = ttk.Button(mainframe, text="Search", command=self.ssdp_search)
        self.button.grid(column=0, row=0, sticky='new')

        self.tree.tag_configure("local",
                                font=font.Font(size=font.nametofont('TkTextFont').actual()['size'],
                                               weight='bold'))

        self.root.bind("<Return>", self.ssdp_search)

        for child in mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        # bind left-click to 'open_link'
        self.tree.bind("<Double-Button-1>", self.open_link)

        # bind right-click to 'change_ip'
        self.tree.bind("<Button-3>", self.do_popup)

        # test
        self.menu = Menu(self.root, tearoff=0)

        # store event for using in clicking callbacks
        self.event = None

    def do_popup(self, event):
        try:
            self.event = event
            self.menu.delete(0, 2)
            self.menu.add_command(label="Change settings..", command=self.change_ip_click)
            self.menu.add_separator()
            self.menu.add_command(label="Properties")
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def open_link(self, event):
        tree = event.widget  # get the treeview widget
        region = tree.identify_region(event.x, event.y)
        col = tree.identify_column(event.x)
        iid = tree.identify('item', event.x, event.y)
        if region == 'cell' and col == '#3':
            link = tree.item(iid)['values'][2]  # get the link from the selected row
            tags = tree.item(iid)['tags'][0]
            if tags == "local":
                wb.open_new_tab(link)  # open the link in a browser tab
                print(tree.item(iid)['values'][3])
            else:
                print("Can't open this link.")
                print(tree.item(iid)['values'][3])

    def ssdp_search(self):
        # M-Search message body
        MS = \
            'M-SEARCH * HTTP/1.1\r\n' \
            'HOST:239.255.255.250:1900\r\n' \
            'ST:upnp:rootdevice\r\n' \
            'MX:2\r\n' \
            'MAN:"ssdp:discover"\r\n' \
            '\r\n'

        for i in self.tree.get_children():
            self.tree.delete(i)

        self.tree.update()

        self.button["state"] = "disabled"
        self.button["text"] = "Searching..."
        self.button.update()

        devices = set()

        adapters = ifaddr.get_adapters()

        index = 1
        device_number = 1

        for adapter in adapters:
            if len(devices) > 0:
                break
            for ip in adapter.ips:
                if not isinstance(ip.ip, str):
                    continue

                if ip.ip == '127.0.0.1':
                    continue

                # Send M-Search message to multicast address for UPNP
                SOC = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                try:
                    SOC.bind((ip.ip, 0))
                except:
                    # print('   Can\'t bind to this ip')
                    continue

                # set timeout
                SOC.settimeout(2)
                try:
                    SOC.sendto(MS.encode('utf-8'), ("239.255.255.250", 1900))
                except OSError as err:
                    print(err)
                    continue

                # listen and capture returned responses
                try:
                    while True:
                        data, addr = SOC.recvfrom(8192)
                        data_dict = self.parse_ssdp_data(data.decode('utf-8'))

                        # if we have not recieved this location before
                        if not data_dict["location"] in devices:
                            devices.add(data_dict["location"])
                            # text_box.config(state='normal')

                            # TODO: return
                            #data_dict = parse_ssdp_data(data.decode('utf-8'))
                            xml_dict = self.parse_upnp_xml(data_dict["location"])
                            # xml_dict = None

                            if xml_dict is not None:
                                self.tree.insert(parent='', index=str(device_number), iid=index, text="",
                                                 values=(str(device_number), data_dict["server"],
                                                         "http://"+addr[0]+xml_dict["presentationURL"], data_dict["uuid"]))
                                self.tree.item(index, tags="local")
                                self.tree.insert(parent=str(index), index='end', iid=index + 1, text="",
                                                 values=("", "  Serial number: " + xml_dict["serialNumber"], ""))
                                self.tree.insert(parent=str(index), index='end', iid=index + 2, text="",
                                                 values=("", "  Firmware version: " + data_dict["version"], ""))
                                index += 3
                            else:
                                self.tree.insert(parent='', index=str(device_number), iid=index, text="",
                                                 values=(str(device_number), data_dict["server"], data_dict["ssdp_url"], data_dict["uuid"]))
                                self.tree.item(index, tags="not_local")
                                self.tree.insert(parent=str(index), index='end', iid=index + 1, text="",
                                                 values=("", "  Firmware version: " + data_dict["version"], ""))
                                index += 2
                            self.tree.update()


                            device_number += 1

                except socket.timeout:
                    SOC.close()
                    # pass
                    if len(devices) > 0:
                        break
                    else:
                        pass

        # now do the old search and get devices there

        old_devices = self.old_search(devices)

        for device in old_devices:
            self.tree.insert(parent='', index=str(device_number), iid=index, text="",
                             values=(str(device_number), '', "http://"+device+":8080", ''))
            self.tree.item(index, tags="local")

            self.tree.update()
            index += 1
            device_number += 1


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

                if words_string[0].lower() == Revealer2.SSDP_HEADER_SERVER:  # format: SERVER: lwIP/1.4.1 UPnP/2.0 8SMC5-USB/4.7.7
                    words_string = string.split(' ')
                    server_version = words_string[len(words_string)-1]  # last word after ' '
                    server_version_words = server_version.split('/')
                    # TODO: we need try/except here
                    ssdp_dict["server"] = server_version_words[0]
                    try:
                        ssdp_dict["version"] = server_version_words[1]
                    except IndexError:
                        ssdp_dict["version"] = '-'

                elif words_string[0].lower() == Revealer2.SSDP_HEADER_LOCATION:  # format: LOCATION: http://172.16.130.67:80/Basic_info.xml
                    words_string = string.split(':')  # do this again for symmetry
                    if words_string[1][0] != ' ':  # we should check if we have ' ' here and not take it to the location string
                        ssdp_dict["location"] = words_string[1] + ':' + words_string[2] + ':' + words_string[3]
                    else:
                        ssdp_dict["location"] = words_string[1][1::1] + ':' + words_string[2] + ':' + words_string[3]

                    ssdp_dict["ssdp_url"] = words_string[2][2::1]  # save only IP  addr

                elif words_string[0].lower() == Revealer2.SSDP_HEADER_USN:  # format: USN: uuid:40001d0a-0000-0000-8e31-4010900b00c8::upnp:rootdevice
                    words_string = string.split(':')  # do this again for symmetry
                    ssdp_dict["uuid"] = words_string[2]

        return ssdp_dict

    @staticmethod
    def parse_upnp_xml(url):
        xml_dict = {}

        try:
            response = urllib.request.urlopen(url, timeout=0.1).read().decode('utf-8')
            data = response.split('\r\n\r\n')  # we need to get rid of the headers
            # print(data[len(data)-1])
            tree = ET.fromstring(data[len(data)-1])

            for child in tree:
                tag_array = child.tag.split('}')
                tag_name = tag_array[len(tag_array)-1]
                xml_dict[tag_name] = child.text

                # print(f'Tag: {child.tag}, text: {child.text}')

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
        MS = \
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
                SOC = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                try:
                    SOC.bind((ip.ip, 0))
                except:
                    # print('   Can\'t bind to this ip')
                    continue

                SOC.settimeout(1)
                try:
                    SOC.sendto(MS.encode('utf-8'), ("239.255.255.250", 1900))
                except OSError as err:
                    print(err)
                    continue

                # listen and capture returned responses
                try:
                    while True:
                        data, addr = SOC.recvfrom(8192)
                        data_dict = self.parse_ssdp_data(data.decode('utf-8'))

                        # if we have not received this location before
                        if not data_dict["location"] in devices:
                            devices.add(data_dict["location"])

                except socket.timeout:
                    SOC.close()
                    if len(devices) > 0:
                        break
                    pass

        # if we received an answer - we have not broken the device (at least)
        # so delete it from the list
        if len(devices) > 0:
            mb.showinfo(
                "Change settings...", "Success.\nNew settings were applied.\nPlease update list of the devices to find this device with the new IP address.",
                parent=self.root
            )
            self.tree.delete(iid)
            self.tree.update()
        else:
            mb.showerror(
                "Change settings...", "Error.\nSomething went wrong while setting new settings.\nPlease check inserted values and try again.", parent=self.root
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


    def get_page_title(self, url):
        title = ""
        try:
            response = urllib.request.urlopen(url, timeout=0.3).read().decode('utf-8')

            data = response.split('title>')  # we need to get rid of the headers
            data = response[response.find('<title>') + 7 : response.find('</title>')]
            print(data)

            return title

        except urllib.error.URLError:
            # print('can\'t open')
            return title

    def old_search(self, ssdp_devices):
        """
        Perform old version of searching devices in the local network as in the revealer 0.1.0
        Sends multicast packet with special string and listen for the answers.
        :return:
        """

        devices = set()

        interfaces = socket.getaddrinfo(host=socket.gethostname(), port=None, family=socket.AF_INET)
        allips = [ip[4][0] for ip in interfaces]

        for ip in allips:
            if not isinstance(ip, str):
                continue

            if ip == '127.0.0.1':
                continue

            # Send M-Search message to multicast address for UPNP
            SOC = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            SOC.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            try:
                SOC.bind((ip, 0))
            except:
                # print('   Can\'t bind to this ip')
                continue

            try:
                MS = "DISCOVER_CUBIELORD_REQUEST " + str(SOC.getsockname()[1])
            except:
                print('error while getting socket port number')

            SOC.settimeout(2)
            try:
                SOC.sendto(MS.encode('utf-8'), ("255.255.255.255", 8008))
            except OSError as err:
                print(err)
                continue

            # listen and capture returned responses
            try:
                while True:
                    data, addr = SOC.recvfrom(8192)
                    if addr[0] not in devices and addr[0] not in ssdp_devices:
                        devices.add(addr[0])
                        print(addr[0])
                        # self.get_page_title("http://" + addr[0] + ":8080")
                    #data_dict = self.parse_ssdp_data(data.decode('utf-8'))

                    # if we have not received this location before
                    #if not data_dict["location"] in devices:
                     #   devices.add(data_dict["location"])

            except socket.timeout:
                SOC.close()
                if len(devices) > 0:
                    break
                pass

        return devices


if __name__ == '__main__':
    print("Start Revealer 2... Version " + Version.full + ".")
    app = Revealer2()
    app.root.mainloop()
