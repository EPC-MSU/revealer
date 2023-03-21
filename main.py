from tkinter import *
from tkinter import ttk

import os
import platform

import socket
import ifaddr


# TODO: maybe we should check this theoretically
def check_ping(hostname, attempts=1, silent=False):
    parameter = '-n' if platform.system().lower() == 'windows' else '-c'
    filter = ' | findstr /i "TTL"' if platform.system().lower() == 'windows' else ' | grep "ttl"'
    if silent:
        silent = ' > NUL' if platform.system().lower() == 'windows' else ' >/dev/null'
    else:
        silent = ''
    response = os.system('ping ' + parameter + ' ' + str(attempts) + ' ' + hostname + filter + silent)

    if response == 0:
        return True
    else:
        return False


def ssdp_search():
    # M-Search message body
    MS = \
        'M-SEARCH * HTTP/1.1\r\n' \
        'HOST:239.255.255.250:1900\r\n' \
        'ST:upnp:rootdevice\r\n' \
        'MX:2\r\n' \
        'MAN:"ssdp:discover"\r\n' \
        '\r\n'

    for i in my_tree.get_children():
        my_tree.delete(i)

    devices = set()

    adapters = ifaddr.get_adapters()

    for adapter in adapters:
        for ip in adapter.ips:
            if not isinstance(ip.ip, str):
                continue

            # Send M-Search message to multicast address for UPNP
            SOC = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            try:
                SOC.bind((ip.ip, 0))
            except:
                # print('   Can\'t bind to this ip')
                continue

            SOC.settimeout(2)
            SOC.sendto(MS.encode('utf-8'), ("239.255.255.250", 1900))

            index = 1
            device_n = 1
            # listen and capture returned responses
            try:
                while True:
                    data, addr = SOC.recvfrom(8192)
                    if not (addr[0] in devices):
                        devices.add(addr[0])
                        # text_box.config(state='normal')
                        data_dict = parse_ssdp_data(data.decode('utf-8'))
                        my_tree.insert(parent='', index='1', iid=index, text=data_dict["server"], values=("", addr[0], str(device_n)))
                        my_tree.insert(parent=str(index), index='end', iid=index+1, text=data_dict["version"], values=(data_dict["version"], data_dict["location"], data_dict["uuid"]))
                        print(parse_ssdp_data(data.decode('utf-8')))
                        index += 2
                        device_n += 1
                        # text_box.config(state='disabled')
            except socket.timeout:
                # print ('No more answers')
                SOC.close()
                pass
    return

SSDP_HEADER_HTTP = "http"
SSDP_HEADER_SERVER = "server"
SSDP_HEADER_LOCATION = "location"
SSDP_HEADER_USN = "usn"

def parse_ssdp_data(ssdp_data):
    ssdp_dict = {"server": "", "version": "", "location": "", "uuid": ""}
    ssdp_strings = ssdp_data.split("\r\n")

    for string in ssdp_strings:
        if string[0:3].lower() != SSDP_HEADER_HTTP:
            words_string = string.split(':')

            if words_string[0].lower() == SSDP_HEADER_SERVER:  # format: SERVER: lwIP/1.4.1 UPnP/2.0 8SMC5-USB/4.7.7
                words_string = string.split(' ')
                server_version = words_string[len(words_string)-1]  # last word after ' '
                server_version_words = server_version.split('/')
                # TODO: we need try/except here
                ssdp_dict["server"] = server_version_words[0]
                ssdp_dict["version"] = server_version_words[1]

            elif words_string[0].lower() == SSDP_HEADER_LOCATION:  # format: LOCATION: http://172.16.130.67:80/Basic_info.xml
                words_string = string.split(':')  # do this again for symmetry
                if words_string[1][0] != ' ':  # we should check if we have ' ' here and not take it to the location string
                    ssdp_dict["location"] = words_string[1] + ':' + words_string[2] + ':' + words_string[3]
                else:
                    ssdp_dict["location"] = words_string[1][1::1] + ':' + words_string[2] + ':' + words_string[3]

            elif words_string[0].lower() == SSDP_HEADER_USN:  # format: USN: uuid:40001d0a-0000-0000-8e31-4010900b00c8::upnp:rootdevice
                words_string = string.split(':')  # do this again for symmetry
                ssdp_dict["uuid"] = words_string[2]

    return ssdp_dict


if __name__ == '__main__':

    # just test zone
    print(check_ping('172.16.130.152', silent=True))

    # devices_list = ssdp_search()

    root = Tk()
    root.title("Revealer 2")
    root.minsize(250, 100)

    # message = devices_list

    mainframe = ttk.Frame(root, padding="3 3 12 12")
    mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    # try with tree
    my_tree = ttk.Treeview(mainframe)
    my_tree.grid(column=1, row=2, sticky=S)

    # Define the columns
    my_tree['columns'] = ("Device", "URL", "ID")
    my_tree.column("#0", width=250, minwidth=100)
    my_tree.column("#1", width=0, stretch="No")
    my_tree.column("URL", anchor=W, minwidth=100)
    my_tree.column("ID", anchor=CENTER, minwidth=80)

    # Create Headings
    my_tree.heading("#0", text="Device", anchor=W)
    my_tree.heading("#1", text="", anchor=W)
    my_tree.heading("URL", text="URL", anchor=CENTER)
    my_tree.heading("ID", text="ID", anchor=CENTER)

    ttk.Button(mainframe, text="Search", command=ssdp_search).grid(column=1, row=1, sticky=N)

    # root.bind("<Return>", ssdp_search(text_box))

    for child in mainframe.winfo_children():
        child.grid_configure(padx=5, pady=5)

    root.mainloop()
