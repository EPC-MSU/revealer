import os
import re
import logging as log

import random

from tkinter import Tk, Frame, Label, Canvas, PhotoImage, LabelFrame, TclError, HORIZONTAL, VERTICAL, LEFT, Entry, \
    Checkbutton, Button, ACTIVE, END, IntVar
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
from thread import ProcessThread
import traceback

from version import Version
from revealertable import RevealerTable
from revealerdevice import RevealerDeviceTag, RevealerDeviceType

DEFAULT_TEXT_COLOR = "black"
CURSOR_POINTER = "hand2"
CURSOR_POINTER_MACOS = "pointinghand"
DEFAULT_BG_COLOR = "white"


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

    MULTICAST_SSDP_PORT = 1900

    # time for redrawing all widgets in milliseconds
    UPDATE_TIME_MS = 250

    # To add support of our new device add it in ths dictionary
    #
    # Format: "Name of its SSDP-server": "version of the firmware from which setting IP via multicast is supported"
    # If this device is not supporting setting IP address via multicast yet just leave this string blank and put "".
    #
    # Take note that "Name of its SSDP-server" must be equal to the name in the SERVER string which this device is
    # sending to the SSDP M_SEARCH.
    # OUR_DEVICE_DICT = {"8SMC5-USB": "4.7.8", "Eth232-4P": "1.0.13", "mDrive": "6.0.1"}

    SSDP_ENHANCED_DEVICES = [
        SSDPEnhancedDevice(
            ssdp_device_name="8SMC5-USB",
            enhanced_ssdp_support_min_fw="4.7.9",
            enhanced_ssdp_version="1.0.0"
        ),
        SSDPEnhancedDevice(
            ssdp_device_name="Eth232-4P",
            enhanced_ssdp_support_min_fw="1.0.13",
            enhanced_ssdp_version="1.0.0"
        ),
        SSDPEnhancedDevice(
            ssdp_device_name="mDrive",
            enhanced_ssdp_support_min_fw="6.0.1",
            enhanced_ssdp_version="1.0.0"
        )
    ]

    def __init__(self):

        # some search initial objects
        self._notify_stop_flag = False

        # tk initial objects
        self.root = Tk(className="revealer")

        self.root.title("Revealer " + Version.full)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.root.propagate(False)

        self.root.geometry("580x400")

        self.root.minsize(width=500, height=200)

        # try to use mac os specific cursor - if exception is raised we are not on mac os and should use default
        self.pointer_cursor = CURSOR_POINTER_MACOS
        try:
            test_label = Label(self.root, text='', cursor=self.pointer_cursor)
            test_label.destroy()
        except TclError:
            self.pointer_cursor = CURSOR_POINTER

        # add revealer icon
        try:
            self.root.iconphoto(False, PhotoImage(file=os.path.join(os.path.dirname(__file__),
                                                                    "resources/appicon.png")))
        except Exception:
            pass

        mainframe = ttk.Frame(self.root, padding="8 3 8 8")
        mainframe.grid(column=0, row=0, sticky="news")

        mainframe.grid_rowconfigure(1, weight=1)
        mainframe.grid_columnconfigure(0, weight=1)

        mainframe.propagate(False)

        # add Search-button
        self.button = ttk.Button(mainframe, text="Search", command=self.start_thread_search, cursor=self.pointer_cursor)
        self.button.grid(column=0, row=0, sticky='new')

        self.main_table = RevealerTable(mainframe, col=0, row=1, height=300, left_click_url_func=self.open_link,
                                        settings_func=self.change_ip_click,
                                        properties_view_func=self.view_prop)

        for child in mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        # store event for using in clicking callbacks
        self.event = None

        # prepare notify socket for correct working
        self.sock_notify = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock_notify.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
        self.sock_notify.bind(('', self.MULTICAST_SSDP_PORT))

        self.info = ""

        self._update_table_thread = ProcessThread()
        self._update_table_thread.start()

        self._ssdp_search_thread = ProcessThread()
        self._ssdp_search_thread.start()

        self._old_search_thread = ProcessThread()
        self._old_search_thread.start()

        self._notify_search_thread = ProcessThread()
        self._notify_search_thread.start()

        self._destroy_flag = threading.Event()
        self._in_process = threading.Event()
        # thread safe event to indicate that we need to update main table one time after search is ended
        self._in_process_after = threading.Event()

        self._changing_settings = threading.Event()
        self.buttons_state_changed = False
        self.table_buttons_state_changed = False

    def __del__(self):
        self.sock_notify.close()

    def update_window(self):
        """
        Method for updating window state in the main thread. It is important to not use anything GUI-related in the
        different threads to avoid closing problems.

        :return:
        """
        # update buttons
        self.update_buttons()
        # update table
        self.update_main_table()
        # update table buttons after
        self.update_table_buttons()
        # reschedule
        self.root.after(self.UPDATE_TIME_MS, self.update_window)

    def update_main_table(self):
        """
        Method for updating main table with current lists of the devices.

        :return:
        """

        if self._in_process.is_set():
            self.main_table.update()
            self.root.update_idletasks()
            self.main_table.delete_to_widget(0)
        elif self._in_process_after.is_set():
            self._in_process_after.clear()
            self.main_table.update()
            self.root.update_idletasks()
            self.main_table.delete_to_widget(0)
        return

    def update_buttons(self):
        if self._in_process.is_set():
            self.button["state"] = "disabled"
            self.button["text"] = "Searching..."
            self.button["cursor"] = ""
            self.button.update()
            self.buttons_state_changed = True
        elif self._changing_settings.is_set():
            self.button["state"] = "disabled"
            self.button["text"] = "Search"
            self.button["cursor"] = ""
            self.button.update()
            self.buttons_state_changed = True
        elif self.buttons_state_changed:
            self.button["state"] = "normal"
            try:
                self.button["cursor"] = CURSOR_POINTER_MACOS
            except TclError:
                self.button["cursor"] = CURSOR_POINTER
            self.button["text"] = "Search"
            self.button.update()
            self.buttons_state_changed = False

    def update_table_buttons(self):
        if self._in_process.is_set():
            self.table_buttons_state_changed = True
        elif self._changing_settings.is_set():
            self.table_buttons_state_changed = True
            self.main_table.disable_all_buttons()
        elif self.table_buttons_state_changed:
            self.table_buttons_state_changed = False
            self.main_table.enable_all_buttons()

    def on_closing(self):
        if mb.askokcancel("Quit", "Do you want to quit?"):
            self._destroy_flag.set()
            # close all threads first
            self._update_table_thread.stop_thread()
            self._ssdp_search_thread.stop_thread()
            self._old_search_thread.stop_thread()
            self._notify_search_thread.stop_thread()

            del self._update_table_thread
            del self._ssdp_search_thread
            del self._old_search_thread
            del self._notify_search_thread

            self.sock_notify.close()
            # and only after this - kill the app
            self.root.destroy()

    def print_i(self, string):
        if len(self.info) > 0:
            self.info += "\n\n"
        self.info += string

    def show_info(self):
        """
        Method for catching exceptions and showing them in separate windows.
        :param args:
        :return:
        """
        if len(self.info) > 0 and not self._destroy_flag.is_set():
            mb.showerror('Error', self.info)

    def start_thread_search(self):

        # remove everything from our table
        self.main_table.delete_all_rows()
        # and delete all devices from the device list of the table
        self.main_table.device_list.clear_all()

        self.info = ""

        # search_thread = threading.Thread(target=self.ssdp_search_task)
        # old_search_thread = threading.Thread(target=self.old_search_task)

        # search_thread.start()
        # old_search_thread.start()

        self._ssdp_search_thread.add_task(self.ssdp_search_task)
        self._old_search_thread.add_task(self.old_search_task)

    def find_ssdp_enhanced_device(self, device_name):
        index = 0

        while index < len(self.SSDP_ENHANCED_DEVICES):
            if self.SSDP_ENHANCED_DEVICES[index].ssdp_device_name.lower() == device_name.lower():
                return index

            index += 1

        return None

    def view_prop(self, prop_dict, link):
        try:
            # if we have local SSDP device
            name = prop_dict['friendlyName']
            PropDialog(name, prop_dict, link, parent=self.root)
        except KeyError:
            try:
                # if we have not local SSDP device
                name = prop_dict['server']
                PropDialog(name, prop_dict, link, parent=self.root)
            except KeyError:
                print('No properties for this device')
                pass

    def view_prop_old(self):
        tree = self.event.widget  # get the treeview widget

        if tree.winfo_class() == "Treeview":
            region = tree.identify_region(self.event.x, self.event.y)
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
                    if tags == RevealerDeviceTag.LOCAL or tags == RevealerDeviceTag.OLD_LOCAL:
                        wb.open_new_tab(link)  # open the link in a browser tab
                    else:
                        print("Can't open this link.")
            else:
                if region == 'cell':
                    if tags == RevealerDeviceTag.LOCAL or tags == RevealerDeviceTag.OLD_LOCAL:
                        wb.open_new_tab(link)  # open the link in a browser tab
                    else:
                        print("Can't open this link.")

        if tree.winfo_class() == 'Label':
            if hasattr(tree, 'link') and hasattr(tree, 'tag'):
                if tree.tag == RevealerDeviceTag.LOCAL or tree.tag == RevealerDeviceTag.OLD_LOCAL:
                    wb.open_new_tab(tree.link)  # open the link in a browser tab
                else:
                    print("Can't open this link.")

    def _listen_and_capture_returned_responses_url(self, sock: socket.socket, devices):
        try:
            while not self._destroy_flag.is_set():
                data, addr = sock.recvfrom(8192)
                data_dict = self.parse_ssdp_data(data.decode('utf-8'), addr)
                # if we have not received this location before
                if not data_dict["ssdp_url"] in devices and data_dict["server"] != "":
                    devices.add(data_dict["ssdp_url"])
                    # threading.Thread(target=self.add_new_item_task, args=[data_dict, addr]).start()
                    self._update_table_thread.add_task(self.add_new_item_task, data_dict, addr)
        except socket.timeout:
            pass
        except OSError:
            pass

        self._notify_stop_flag = True
        sock.close()

    def ssdp_search_task(self):
        # M-Search message body
        message = \
            'M-SEARCH * HTTP/1.1\r\n' \
            'HOST:239.255.255.250:1900\r\n' \
            'ST:upnp:rootdevice\r\n' \
            'MX:1\r\n' \
            'MAN:"ssdp:discover"\r\n' \
            '\r\n'

        try:
            if not self._destroy_flag.is_set():
                self._in_process.set()
                self._in_process_after.set()
            else:
                return

            devices = set()

            adapters = ifaddr.get_adapters()

            for adapter in adapters:
                for ip in adapter.ips:
                    if self._destroy_flag.is_set():
                        return
                    if not isinstance(ip.ip, str):
                        continue

                    if ip.ip == '127.0.0.1':
                        continue

                    # Send M-Search message to multicast address for UPNP
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                    try:
                        sock.bind((ip.ip, 0))
                    except Exception:
                        continue

                    # if ip.ip is suitable for m-search - try to listen for notify messages also
                    # notify_listen_thread = threading.Thread(target=self.listen_notify_task, args=[ip.ip])
                    # notify_listen_thread.start()
                    self._notify_search_thread.add_task(self.listen_notify_task, ip.ip)

                    # set timeout
                    sock.settimeout(1)
                    try:
                        sock.sendto(message.encode('utf-8'), ("239.255.255.250", 1900))
                    except OSError:
                        continue

                    self._listen_and_capture_returned_responses_url(sock, devices)

            self._in_process.clear()

        except Exception:
            except_info = traceback.format_exc()
            self.print_i(f"Unhandled exception occurred while performing SSDP search:\n{except_info}")

        # show info from search if we had some important information (exceptions with errors)
        # TODO: move to the update window method ??
        if not self._destroy_flag.is_set():
            self.show_info()

        return

    def add_new_item_task(self, data_dict, addr, notify_flag=False):

        try:
            xml_dict = self.parse_upnp_xml(data_dict["location"])

            # check is this our device or not
            version_with_settings = ""

            device_index_in_list = self.find_ssdp_enhanced_device(data_dict["server"])

            if device_index_in_list is not None:
                version_with_settings = \
                    self.SSDP_ENHANCED_DEVICES[device_index_in_list].enhanced_ssdp_support_min_fw
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

            else:
                if not notify_flag:
                    uuid = None
                    pass
                else:
                    # if this is not our device - we don't need its notify message
                    return

            if xml_dict is not None:
                # check that we have our url with correct format
                try:
                    if xml_dict["presentationURL"][0:4] != "http":
                        link = "http://" + addr[0] + xml_dict["presentationURL"]
                    else:
                        link = xml_dict["presentationURL"]
                except KeyError:
                    xml_dict["presentationURL"] = "None"
                    link = "http://" + addr[0]

                xml_dict["version"] = data_dict["version"]

                if not self._destroy_flag.is_set():
                    with self.main_table.lock:
                        # self.main_table.move_table_rows(self.main_table.last_row)
                        self.main_table.add_row_ssdp_item(xml_dict["friendlyName"],
                                                          link, data_dict["ssdp_url"], uuid, xml_dict,
                                                          tag=RevealerDeviceTag.LOCAL)
            else:
                if not self._destroy_flag.is_set():
                    with self.main_table.lock:
                        # self.main_table.move_table_rows(self.main_table.last_row)
                        self.main_table.add_row_ssdp_item(data_dict["server"],
                                                          data_dict["ssdp_url"], data_dict["ssdp_url"],
                                                          uuid, data_dict, tag=RevealerDeviceTag.NOT_LOCAL)
        except Exception:
            except_info = traceback.format_exc()
            self.print_i(f"Error while trying to add new device {addr} with data_dict {data_dict} to the table:\n"
                         f"{except_info}")

    def socket_notify_reinit(self):
        return

    def listen_notify_task(self, interface_ip):
        """
        Task for search thread where we listen for all notify messages while we sending m-searches since we add too
        our device option to send notify with answering to the m-search.
        :return:
        """

        multicast_group = '239.255.255.250'

        try:
            self.sock_notify.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP,
                                        socket.inet_aton(multicast_group) + socket.inet_aton(interface_ip))
        except OSError:
            pass

        # we are starting the task so flag should be False
        self._notify_stop_flag = False

        # listen and capture returned responses
        try:
            while not self._notify_stop_flag and not self._destroy_flag.is_set():
                data, addr = self.sock_notify.recvfrom(8192)
                data_strings = data.decode('utf-8').split('\r\n')

                if data_strings[0] == 'NOTIFY * HTTP/1.1':
                    data_dict = self.parse_ssdp_data(data.decode('utf-8'), addr)

                    # threading.Thread(target=self.add_new_item_task, args=[data_dict, addr, True]).start()
                    self._update_table_thread.add_task(self.add_new_item_task, data_dict, addr, True)

        except socket.timeout:
            pass
        except OSError:
            pass

    def _parse_ssdp_header_server(self, string, ssdp_dict) -> None:
        words_string = string.split(' ')
        server_version = words_string[len(words_string) - 1]  # last word after ' '
        server_version_words = server_version.split('/')
        try:
            ssdp_dict["server"] = server_version_words[0]
        except IndexError:
            ssdp_dict["server"] = "None"
        try:
            ssdp_dict["version"] = server_version_words[1]
        except IndexError:
            ssdp_dict["version"] = '-'

    def _parse_ssdp_header_location(self, string, ssdp_dict, addr) -> None:
        words_string = string.split(':')  # do this again for symmetry
        if len(words_string) == 2:
            # if in words_string we only have LOCATION and second element without any : in it
            # this means we have invalid LOCATION URL -
            # relative but UPnP standards require absolute URL.
            # See https://openconnectivity.org/upnp-specs/UPnP-arch-DeviceArchitecture-v2.0-20200417.pdf
            # on pages 29 and 41 for LOCATION header format
            #
            # Nevertheless we are trying to get xml-file for this devices with address
            if words_string[1][0] != \
                    ' ':  # we should check if we have ' ' here and not take it to the location string
                ssdp_dict["location"] = 'http://' + addr[0] + ":80" + words_string[1]
            else:
                ssdp_dict["location"] = 'http://' + addr[0] + ":80" + words_string[1][1::1]
            # print(ssdp_dict["location"], addr[0])
            ssdp_dict["ssdp_url"] = addr[0]  # save only IP address
        elif len(words_string) == 4:
            # case with full absolute URL with port specified
            # for example: http://172.16.130.67:80/Basic_info.xml
            if words_string[1][0] != \
                    ' ':  # we should check if we have ' ' here and not take it to the location string
                ssdp_dict["location"] = words_string[1] + ':' + words_string[2] + ':' + words_string[3]
            else:
                ssdp_dict["location"] = words_string[1][1::1] + ':' + words_string[2] + ':' +\
                                        words_string[3]
            ssdp_dict["ssdp_url"] = words_string[2][2::1]  # save only IP address
        elif len(words_string) == 3:
            # case with absolute URL without port specified
            # for example: http://172.16.130.67/Basic_info.xml
            if words_string[1][0] != \
                    ' ':  # we should check if we have ' ' here and not take it to the location string
                ssdp_dict["location"] = words_string[1] + ':' + words_string[2]
            else:
                ssdp_dict["location"] = words_string[1][1::1] + ':' + words_string[2]
            url_parts = words_string[2].split("/")
            # save only IP address (third in //172.16.130.67/Basic_info.xml splitted with '/')
            if len(url_parts) >= 3:
                ssdp_dict["ssdp_url"] = url_parts[2]
            else:
                ssdp_dict["ssdp_url"] = addr
        elif len(words_string) > 4:

            # check that it is absolute address:
            try:
                http_index = words_string[1].index('http')
            except ValueError:
                http_index = -1
                log.debug(f"We have location string from {addr} with URL with incorrect format:"
                            f" {string}. We can not get its location and xml-file.")
                ssdp_dict["ssdp_url"] = words_string[2][2::1]  # save only IP address

            log.debug(f"We found device http_index = {http_index} with long LOCATION: {words_string}")

            if http_index >= 0:
                if words_string[1][0] != \
                        ' ':  # we should check if we have ' ' here and not take it to the location string
                    ssdp_dict["location"] = words_string[1]

                    for i in range(len(words_string)-2):
                        ssdp_dict["location"] += ':' + words_string[i+2]
                else:
                    ssdp_dict["location"] = words_string[1][1::1]
                    for i in range(len(words_string)-2):
                        ssdp_dict["location"] += ':' + words_string[i+2]
                url_parts = ssdp_dict["location"].split("/")
                # save only IP address (third in //172.16.130.67/Basic_info.xml splitted with '/')
                if len(url_parts) >= 3:
                    ssdp_dict["ssdp_url"] = url_parts[2].split(':')[0]
                else:
                    ssdp_dict["ssdp_url"] = addr

                log.debug(f"We found device with long LOCATION: {ssdp_dict['location']}. "
                            f"And got its URL: {ssdp_dict['ssdp_url']}")
        else:
            log.warning(f"We have location string from {addr} with URL with incorrect format:"
                        f" {string}. We can not get its location and xml-file.")
            ssdp_dict["ssdp_url"] = words_string[2][2::1]  # save only IP address

    def _parse_ssdp_headeer_usn(self, string, ssdp_dict, addr) -> None:
        words_string = string.split(':')  # do this again for symmetry
        try:
            ssdp_dict["uuid"] = words_string[2]
        except IndexError:
            except_info = traceback.format_exc()
            self.print_i(f"USN of {addr} has incorrect format: {string}. It should be:\n"
                         f"USN: uuid:00000000-0000-0000-0000-000000000000::<device-type>."
                         f"\n{except_info}")

    def parse_ssdp_data(self, ssdp_data, addr):
        ssdp_dict = {"server": "", "version": "", "location": "", "ssdp_url": "", "uuid": ""}
        ssdp_strings = ssdp_data.split("\r\n")

        try:
            for string in ssdp_strings:
                if string[0:3].lower() != Revealer2.SSDP_HEADER_HTTP:
                    words_string = string.split(':')

                    if words_string[0].lower() \
                            == Revealer2.SSDP_HEADER_SERVER:  # format: SERVER: lwIP/1.4.1 UPnP/2.0 8SMC5-USB/4.7.7
                        self._parse_ssdp_header_server(string, ssdp_dict)
                    elif words_string[0].lower() == \
                            Revealer2.SSDP_HEADER_LOCATION:  # format: LOCATION: http://172.16.130.67:80/Basic_info.xml
                        self._parse_ssdp_header_location(string, ssdp_dict, addr)
                    elif words_string[0].lower() == \
                            Revealer2.SSDP_HEADER_USN:
                        # USN: uuid:40001d0a-0000-0000-8e31-4010900b00c8::upnp:rootdevice
                        self._parse_ssdp_headeer_usn(string, ssdp_dict, addr)
        except Exception:
            except_info = traceback.format_exc()
            self.print_i(f"Error in parsing {addr} SSDP data:\n{except_info}")
            return ssdp_dict

        return ssdp_dict

    @staticmethod
    def parse_upnp_xml(url):
        xml_dict = {}

        try:
            response = urllib.request.urlopen(url, timeout=1).read().decode('utf-8')
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

            return xml_dict

        except Exception:
            return None

    def change_ip_multicast(self, uuid, settings_dict):

        # delete any info from pevious processe
        self.info = ""

        # thread_change = threading.Thread(target=lambda: self.change_ip_multicast_task(uuid, settings_dict))
        # start process for changing settings in another thread
        # thread_change.start()
        # TODO: maybe we need different proccess thread for this changing
        self._ssdp_search_thread.add_task(self.change_ip_multicast_task, uuid, settings_dict)

    def _listen_and_capture_returned_responses_location(self, sock: socket.socket, devices, uuid) -> bool:
        try:
            while not self._destroy_flag.is_set():
                data, addr = sock.recvfrom(8192)
                data_dict = self.parse_ssdp_data(data.decode('utf-8'), addr)

                # if we have not received this location before
                if not data_dict["location"] in devices and data_dict["uuid"] == uuid:
                    devices.add(data_dict["location"])

        except socket.timeout:
            # try to get notify response from different network
            try:
                while not self._destroy_flag.is_set():
                    data_notify, addr_notify = self.sock_notify.recvfrom(8192)
                    data_strings = data_notify.decode('utf-8').split('\r\n')

                    if data_strings[0] == 'NOTIFY * HTTP/1.1':

                        data_notify_dict = self.parse_ssdp_data(data_notify.decode('utf-8'), addr_notify)

                        if not data_notify_dict["location"] in devices and data_notify_dict["uuid"] == uuid:
                            devices.add(data_notify_dict["location"])
            except socket.timeout:
                pass
            except OSError:
                pass

            sock.close()
            if len(devices) > 0:
                # We want to break
                return True
            pass
        except OSError:
            pass
        return False

    def _show_change_settings_info(self, devices):
        if len(devices) > 0:
            mb.showinfo(
                "Change settings...",
                "Success.\nNew settings were applied.\nPlease update list of the devices "
                "to find this device with the new IP address.",
                parent=self.root
            )
        else:
            mb.showerror(
                "Change settings...",
                "Error.\nSomething went wrong while setting new settings."
                "\nPlease check inserted values and try again.",
                parent=self.root
            )

    def _change_ips_of_adapter(self, adapter, message, devices, uuid):
        for ip in adapter.ips:
            if not isinstance(ip.ip, str):
                continue

            if ip.ip == '127.0.0.1':
                continue

            # Send M-Search message to multicast address for UPNP
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            try:
                sock.bind((ip.ip, 0))
            except Exception:
                continue

            # try to listen to the notify too because if we are trying to change something in another network
            multicast_group = '239.255.255.250'

            try:
                self.sock_notify.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP,
                                            socket.inet_aton(multicast_group) + socket.inet_aton(ip.ip))
            except OSError:
                pass

            self.sock_notify.settimeout(0.5)

            sock.settimeout(1)
            try:
                sock.sendto(message.encode('utf-8'), ("239.255.255.250", 1900))
            except OSError:
                continue

            _break = self._listen_and_capture_returned_responses_location(sock, devices, uuid)
            if _break:
                break

    def change_ip_multicast_task(self, uuid, settings_dict):
        """
        Function for changing device's net settings (IP address and network mask) via multicast. We are using same
        protocol as for SSDP M-SEARCH but setting its aim as desired device's UUID and add new header in format:

            MIPAS: 198.16.1.1;255.255.240.0;\r\n

        (MIPAS - Multicast IP Address Setting)

        :param uuid: string
            UUID of the device net settings of which should be modified.
        :param settings_dict: dict
            Dictionary with password and new settings for this device.

        :return:
        """

        # M-Search message body for changing IP address of this current device
        message = \
            'M-SEARCH * HTTP/1.1\r\n' \
            'HOST:239.255.255.250:1900\r\n' \
            'ST:uuid:' + uuid + '\r\n' \
                                'MX:2\r\n' \
                                'MAN:"ssdp:discover"\r\n' \
                                'MIPAS:' + settings_dict['password'] + ';' + str(settings_dict['dhcp']) + ';' \
            + settings_dict['ip'] + ';' + settings_dict['netmask'] + ';' \
            + settings_dict['gateway'] + ';\r\n' \
                                         '\r\n'

        try:
            self._changing_settings.set()

            devices = set()

            adapters = ifaddr.get_adapters()

            for adapter in adapters:
                if len(devices) > 0:
                    break
                self._change_ips_of_adapter(adapter, message, devices, uuid)
            self._show_change_settings_info(devices)

            self._changing_settings.clear()
        except Exception:
            except_info = traceback.format_exc()
            self.print_i(f"Unhandled error while setting device network settings:\n{except_info}")

        # show window with errors if there were any
        self.show_info()

    def change_ip_click(self, name, uuid, link):
        """
        Function for starting IP-address changing by clicking the button.
        :return: None
        """

        dialog = MIPASDialog("Change settings...", name, uuid, parent=self.root)
        if dialog.result is not None:
            try:
                new_settings = dialog.result

                # request changing net settings
                self.change_ip_multicast(uuid, new_settings)
            except ValueError:
                print(f"Errors in inserted values: {dialog.result}")

    @staticmethod
    def get_page_title(url):
        title = ""
        try:
            response = urllib.request.urlopen(url, timeout=0.3).read().decode('utf-8')

            # data = response.split('title>')  # we need to get rid of the headers
            title = response[response.find('<title>') + 7: response.find('</title>')]

            return title

        except urllib.error.URLError:
            return title

    def _listen_and_capture_returned_responses_old(self,
                                                   sock: socket.socket,
                                                   devices,
                                                   ssdp_devices,
                                                   ssdp_device_number) -> bool:
        try:
            while not self._destroy_flag.is_set():
                data, addr = sock.recvfrom(8192)
                if addr[0] not in devices and addr[0] not in ssdp_devices:
                    devices.add(addr[0])

                    title = addr[0]

                    if not self._destroy_flag.is_set():
                        with self.main_table.lock:
                            self.main_table.add_row_old_item(title, "http://" + addr[0],
                                                             tag=RevealerDeviceTag.OLD_LOCAL)

                    for i in range(40):
                        if self._destroy_flag.is_set():
                            sock.close()
                            return True
                        with self.main_table.lock:
                            rand_i = int(random.random() * 40) + i
                            self._update_table_thread.add_task(self.main_table.add_row_old_item,
                                                               title + "." + str(rand_i),
                                                               "http://" + addr[0] + "." + str(rand_i),
                                                               RevealerDeviceTag.OLD_LOCAL)

                    ssdp_device_number += 1

        except socket.timeout:
            sock.close()
            if len(devices) > 0:
                return True
            pass
        except OSError:
            pass

        return False

    def old_search(self, ssdp_devices, device_number):
        """
        Perform old version of searching devices in the local network as in the revealer 0.1.0
        Sends multicast packet with special string and listen for the answers.
        :return:
        """

        try:
            ssdp_device_number = device_number

            devices = set()

            adapters = ifaddr.get_adapters()

            for adapter in adapters:
                for ip in adapter.ips:
                    if not isinstance(ip.ip, str):
                        continue

                    if ip.ip == '127.0.0.1':
                        continue

                    # Send M-Search message to multicast address for UPNP
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    try:
                        sock.bind((ip.ip, 0))
                    except Exception:
                        continue

                    try:
                        message = "DISCOVER_CUBIELORD_REQUEST " + str(sock.getsockname()[1])
                    except Exception:
                        print('error while getting socket port number')
                        continue

                    sock.settimeout(0.5)
                    try:
                        sock.sendto(message.encode('utf-8'), ("255.255.255.255", 8008))
                    except OSError:
                        continue

                    # listen and capture returned responses
                    _break = self._listen_and_capture_returned_responses_old(sock,
                                                                             devices,
                                                                             ssdp_devices,
                                                                             ssdp_device_number)
                    if _break:
                        break
            return devices
        except Exception:
            except_info = traceback.format_exc()
            self.print_i(f"Unhandled error in old protocol search:\n{except_info}")

    def old_search_task(self):
        self.old_search({}, 1)


class MIPASDialog(sd.Dialog):
    NET_MASK_RE = "^(((255\\.){3}(252|248|240|224|192|128|0+))|((255\\.){2}(255|254|252|248|240|224|192|128|0+)\\.0)" \
                  "|((255\\.)(255|254|252|248|240|224|192|128|0+)(\\.0+){2})" \
                  "|((255|254|252|248|240|224|192|128|0+)(\\.0+){3}))$"
    IP_ADDRESS_RE = "^((25[0-5]|(2[0-4]|1\\d|[1-9]|)\\d)\\.?\\b){4}$"

    DEFAULT_ENTRY_IP_TEXT = "192.168.1.1"
    DEFAULT_ENTRY_MASK_TEXT = "255.255.0.0"
    DEFAULT_ENTRY_GATEWAY_TEXT = "192.168.1.1"
    DEFAULT_ENTRY_TEXT_COLOR = "grey"

    ENTRY_STATE_DISABLED = "disabled"
    ENTRY_STATE_NORMAL = "normal"

    def __init__(self, title, device, uuid,
                 initialvalue=None,
                 parent=None):

        self.device = device
        self.uuid = uuid

        self.initialvalue = initialvalue

        self.entry_ip = None
        self.entry_mask = None
        self.entry_password = None

        self.entry_gateway = None

        self.checkbox_dhcp = None
        self.dhcp = IntVar()

        # for macos we may want to change this color to white or just default system color
        self.text_color = "SystemButtonText"

        sd.Dialog.__init__(self, parent, title)

    def entry_click(self, event):
        entry_widget = event.widget

        if entry_widget.default:
            entry_widget.default = False
            entry_widget.delete(0, 'end')
            entry_widget.configure(fg=self.text_color)

    def entry_leave(self, event):
        entry_widget = event.widget

        if entry_widget.get() == "":
            if entry_widget == self.entry_ip:
                default_text = self.DEFAULT_ENTRY_IP_TEXT
            elif entry_widget == self.entry_mask:
                default_text = self.DEFAULT_ENTRY_MASK_TEXT
            elif entry_widget == self.entry_gateway:
                default_text = self.DEFAULT_ENTRY_GATEWAY_TEXT
            else:
                return

            entry_widget.delete(0, 'end')
            entry_widget.configure(fg=self.DEFAULT_ENTRY_TEXT_COLOR)
            entry_widget.insert(0, default_text)

            entry_widget.default = True

    def destroy(self):
        self.entry_ip = None
        self.entry_mask = None
        sd.Dialog.destroy(self)

    def body(self, master):

        # self.minsize(width=300, height=200)

        device_frame = Frame(master)
        device_frame.grid(row=0, column=0, sticky='news')

        Label(device_frame, text="Device: ", justify=LEFT).grid(column=0, row=0, padx=5, sticky='w')
        Label(device_frame, text=self.device, justify=LEFT).grid(column=1, row=0, padx=5, sticky='w')

        if self.uuid != '':
            Label(device_frame, text="UUID: ", justify=LEFT).grid(column=0, row=1, padx=5, sticky='w')
            Label(device_frame, text=self.uuid, justify=LEFT).grid(column=1, row=1, padx=5, sticky='w')

        Label(device_frame, text="Password: ", justify=LEFT).grid(column=0, row=2, padx=5, pady=5, sticky='w')
        self.entry_password = Entry(device_frame, name="entry_password", show="*")
        self.entry_password.grid(column=1, row=2, padx=5, pady=5, sticky='ew')

        # blank row
        Label(master, text="", justify=LEFT).grid(column=0, row=1, padx=5, sticky='w')
        # blank row
        Label(master, text="", justify=LEFT).grid(column=0, row=3, padx=5, sticky='w')

        frame = LabelFrame(master, text="Network settings", fg=self.text_color,
                           font=('TkTextFont', font.nametofont('TkTextFont').actual()['size'], 'bold'))

        frame.grid(row=2, column=0, sticky='ns')

        # row for DHCP state
        Label(frame, text="Get IP from DHCP: ", justify=LEFT).grid(column=0, row=3, padx=8, pady=8, sticky='w')
        self.checkbox_dhcp = Checkbutton(frame, variable=self.dhcp, command=self._dhcp_change_state)
        self.checkbox_dhcp.grid(column=1, row=3, sticky='w')

        # row for IP address
        Label(frame, text="IP address: ", justify=LEFT).grid(column=0, row=4, padx=8, pady=8, sticky='w')
        self.entry_ip = Entry(frame, name="entry_ip", fg=self.DEFAULT_ENTRY_TEXT_COLOR)
        self.entry_ip.grid(column=1, row=4, padx=8, pady=8, sticky='ew')

        # start with the default text
        self.entry_ip.insert(0, self.DEFAULT_ENTRY_IP_TEXT)
        self.entry_ip.select_range(0, END)
        self.entry_ip.bind("<FocusIn>", self.entry_click)
        self.entry_ip.bind("<Button-1>", self.entry_click)
        self.entry_ip.bind("<FocusOut>", self.entry_leave)
        self.entry_ip.default = True

        # row for Net Mask
        Label(frame, text="Network Mask: ", justify=LEFT).grid(column=0, row=5, padx=8, pady=8, sticky='w')
        self.entry_mask = Entry(frame, name="entry_mask", fg=self.DEFAULT_ENTRY_TEXT_COLOR)
        self.entry_mask.grid(column=1, row=5, padx=8, pady=8, sticky='ew')

        # start with the default text
        self.entry_mask.insert(0, self.DEFAULT_ENTRY_MASK_TEXT)
        self.entry_mask.select_range(0, END)
        self.entry_mask.bind("<FocusIn>", self.entry_click)
        self.entry_mask.bind("<Button-1>", self.entry_click)
        self.entry_mask.bind("<FocusOut>", self.entry_leave)
        self.entry_mask.default = True

        # row for Gateway
        Label(frame, text="Default Gateway: ", justify=LEFT).grid(column=0, row=6, padx=8, pady=8, sticky='w')
        self.entry_gateway = Entry(frame, name="entry_gateway", fg=self.DEFAULT_ENTRY_TEXT_COLOR)
        self.entry_gateway.grid(column=1, row=6, padx=8, pady=8, sticky='ew')

        # start with the default text
        self.entry_gateway.insert(0, self.DEFAULT_ENTRY_GATEWAY_TEXT)
        self.entry_gateway.select_range(0, END)
        self.entry_gateway.bind("<FocusIn>", self.entry_click)
        self.entry_gateway.bind("<FocusOut>", self.entry_leave)
        self.entry_gateway.default = True

        self.update()
        self.update_idletasks()

        self.minsize(width=max(device_frame.winfo_width(), frame.winfo_width())+10,
                     height=(device_frame.winfo_height() + frame.winfo_height() + 100))

        return self.entry_password

    def _dhcp_change_state(self):
        if self.dhcp.get():
            self.entry_ip['state'] = 'disabled'
            self.entry_mask['state'] = 'disabled'
            self.entry_gateway['state'] = 'disabled'
        else:
            self.entry_ip['state'] = 'normal'
            self.entry_mask['state'] = 'normal'
            self.entry_gateway['state'] = 'normal'

    def _validate_net_format(self, result_ip: dict) -> str:
        warning_msg = ""
        if self.check_format(result_ip['ip'], self.IP_ADDRESS_RE):
            if len(warning_msg) > 0:
                warning_msg += "\n\n"
            warning_msg += "IP Address format is incorrect.\nRequired format: #.#.#.#, where # stands for" \
                           " number from 0 to 255." \
                           "\nExample: 192.168.1.1."
        if self.check_format(result_ip['netmask'], self.NET_MASK_RE):
            if len(warning_msg) > 0:
                warning_msg += "\n\n"
            warning_msg += "\nNetwork Mask format is incorrect.\nRequired format: #.#.#.#, where # stands for" \
                           " number from 0 to 255.\nExample: 255.255.0.0."
        if result_ip['gateway'] != '' and self.check_format(result_ip['gateway'], self.IP_ADDRESS_RE):
            if len(warning_msg) > 0:
                warning_msg += "\n\n"
            warning_msg += "Gateway Address format is incorrect.\nRequired format: #.#.#.#, where # stands for" \
                           " number from 0 to 255." \
                           "\nExample: 192.168.1.1."
        return warning_msg

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

        # check password length
        if len(result_ip['password']) > 20:
            mb.showwarning(
                "Password is too long",
                "\nPassword of this device can be 20 or less symbols long.",
                parent=self
            )
            return 0

        if result_ip['dhcp'] == 0 and (result_ip['ip'] == '' or result_ip['netmask'] == ''):
            mb.showwarning(
                "Warning",
                "\nPlease insert new IP address and Network Mask or choose DHCP server for IP configuration.",
                parent=self
            )
            return 0

        elif result_ip['dhcp'] == 0:
            warning_msg = self._validate_net_format(result_ip)
            if len(warning_msg) > 0:
                mb.showwarning("Warning", warning_msg, parent=self)
                return 0

        elif result_ip['dhcp'] == 1:
            result_ip['ip'] = '192.168.2.1'
            result_ip['netmask'] = '255.255.0.0'
            result_ip['gateway'] = '192.168.1.1'

        if result_ip['gateway'] == '':
            result_ip['gateway'] = '0.0.0.0'

        self.result = result_ip

        return 1

    def getresult(self):
        result_dict = {'password': self.entry_password.get(), 'dhcp': self.dhcp.get()}

        if not self.entry_ip.default:
            result_dict['ip'] = self.entry_ip.get()
        else:
            result_dict['ip'] = ""

        if not self.entry_mask.default:
            result_dict['netmask'] = self.entry_mask.get()
        else:
            result_dict['netmask'] = ""

        if not self.entry_gateway.default:
            result_dict['gateway'] = self.entry_gateway.get()
        else:
            result_dict['gateway'] = ""

        return result_dict

    @staticmethod
    def check_format(string, re_format) -> bool:

        ip_format = re.compile(re_format)

        if ip_format.match(string) is not None:
            return False
        else:
            return True


class PropDialog(sd.Dialog):
    def __init__(self, device_name, properties_dict, url,
                 parent=None):

        self.name = device_name
        self.url = url

        self.dict = properties_dict

        self.labels_dict = {'friendlyName': 'Friendly name', 'manufacturer': 'Manufacturer',
                            'manufacturerURL': 'Manufacturer URL', 'modelDescription': 'Model description',
                            'modelName': 'Model name', 'modelNumber': 'Model number', 'modelURL': 'Model URL',
                            'serialNumber': 'Serial number', 'UDN': 'UDN', 'presentationURL': 'Presentation URL',
                            'server': 'SSDP server', 'uuid': 'UUID', 'version': 'Firmware version', 'ssdp_url': 'URL'}

        # try to use mac os specific cursor - if exception is raised we are not on mac os and should use default
        self.pointer_cursor = CURSOR_POINTER_MACOS
        try:
            test_label = Label(parent, text='', cursor=self.pointer_cursor)
            test_label.destroy()
        except TclError:
            self.pointer_cursor = CURSOR_POINTER

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
                    Label(master, text=label_name + ": ", justify=LEFT, fg=DEFAULT_TEXT_COLOR,
                          font=('TkTextFont', font.nametofont('TkTextFont').actual()['size'],
                                'bold')).grid(column=0, row=row_index, padx=5, sticky='w')
                    if name == 'presentationURL':
                        Label(master, text=self.url, justify=LEFT, cursor=self.pointer_cursor, fg=DEFAULT_TEXT_COLOR,
                              font=('TkTextFont', font.nametofont('TkTextFont').actual()['size'], 'underline')).grid(
                            column=1, row=row_index, padx=5, sticky='w')
                    else:
                        if self.dict[name][0:4] == "http":
                            font_style = 'underline'
                            cursor = self.pointer_cursor
                        Label(master, text=self.dict[name], justify=LEFT, cursor=cursor, fg=DEFAULT_TEXT_COLOR,
                              font=('TkTextFont', font.nametofont('TkTextFont').actual()['size'], font_style)).grid(
                            column=1, row=row_index, padx=5, sticky='w')
                    row_index += 1
                except KeyError:
                    pass

        self.bind("<Button-1>", self.open_link)

        self.update()
        self.update_idletasks()

        self.minsize(width=self.winfo_width()*2,
                     height=self.winfo_height()+75)

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
    app.root.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.root.after(app.UPDATE_TIME_MS, app.update_window)
    app.root.mainloop()
