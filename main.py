from tkinter import *
from tkinter import ttk, font

import socket
import ifaddr
import webbrowser as wb

import xml.etree.ElementTree as ET
import urllib.request

from version import Version


class Revealer2:

    SSDP_HEADER_HTTP = "http"
    SSDP_HEADER_SERVER = "server"
    SSDP_HEADER_LOCATION = "location"
    SSDP_HEADER_USN = "usn"

    def __init__(self):

        self.root = Tk()
        self.root.title("Revealer 2 " + Version.full)

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
        self.tree['columns'] = ("#", "Device", "URL")
        self.tree.column("#0", anchor=W, width=20, minwidth=20, stretch=NO)
        self.tree.column("#", anchor=CENTER, width=30, minwidth=30, stretch=NO)
        self.tree.column("Device", anchor=W, minwidth=150)
        self.tree.column("URL", anchor=W, minwidth=250)

        # Create Headings
        self.tree.heading("#0", text="", anchor=W)
        self.tree.heading("#", text="#", anchor=CENTER)
        self.tree.heading("URL", text="URL", anchor=CENTER)
        self.tree.heading("Device", text="Device", anchor=CENTER)

        self.button = ttk.Button(mainframe, text="Search", command=self.ssdp_search)
        self.button.grid(column=0, row=0, sticky='new')

        self.tree.tag_configure("local",
                                font=font.Font(size=font.nametofont('TkTextFont').actual()['size'],
                                               weight='bold'))

        self.root.bind("<Return>", self.ssdp_search)

        for child in mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        # bind left-click to 'open_link'
        self.tree.bind('<Button-1>', self.open_link)

    @staticmethod
    def open_link(event):
        tree = event.widget  # get the treeview widget
        region = tree.identify_region(event.x, event.y)
        col = tree.identify_column(event.x)
        iid = tree.identify('item', event.x, event.y)
        if region == 'cell' and col == '#3':
            link = tree.item(iid)['values'][2]  # get the link from the selected row
            tags = tree.item(iid)['tags'][0]
            if tags == "local":
                wb.open_new_tab(link)  # open the link in a browser tab
            else:
                print("Can't open this link.")

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

                            if xml_dict is not None:
                                self.tree.insert(parent='', index=str(device_number), iid=index, text="",
                                                 values=(str(device_number), data_dict["server"],
                                                         "http://"+addr[0]+xml_dict["presentationURL"]))
                                self.tree.item(index, tags="local")
                                self.tree.insert(parent=str(index), index='end', iid=index + 1, text="",
                                                 values=("", "  Serial number: " + xml_dict["serialNumber"], ""))
                                self.tree.insert(parent=str(index), index='end', iid=index + 2, text="",
                                                 values=("", "  Firmware version: " + data_dict["version"], ""))
                                index += 3
                            else:
                                self.tree.insert(parent='', index=str(device_number), iid=index, text="",
                                                 values=(str(device_number), data_dict["server"], data_dict["ssdp_url"]))
                                self.tree.item(index, tags="not_local")
                                self.tree.insert(parent=str(index), index='end', iid=index + 1, text="",
                                                 values=("", "  Firmware version: " + data_dict["version"], ""))
                            self.tree.update()

                            index += 3
                            device_number += 1

                except socket.timeout:
                    SOC.close()
                    pass

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
            response = urllib.request.urlopen(url, timeout=0.2).read().decode('utf-8')
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


if __name__ == '__main__':
    print("Start Revealer 2... Version " + Version.full + ".")
    app = Revealer2()
    app.root.mainloop()
