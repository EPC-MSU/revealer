import os
import re
import logging as log

import time

from tkinter import Tk, Frame, Label, PhotoImage, LabelFrame, TclError, LEFT, Entry, \
    Checkbutton, Button, ACTIVE, IntVar, Toplevel
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
from thread import ProcessThread, SSDPSearchThread, ParseDevicesThread
import traceback

from version import Version
from revealertable import RevealerTable
from revealerdevice import RevealerDeviceTag

DEFAULT_TEXT_COLOR = "black"
CURSOR_POINTER = "hand2"
CURSOR_POINTER_MACOS = "pointinghand"
DEFAULT_BG_COLOR = "white"

URL_REGEX_PORT = "https?:\\/\\/((25[0-5]|(2[0-4]|1\\d|[1-9]|)\\d)\\.?\\b){4}:\\d{1,5}"
URL_REGEX_WITHOUT_PORT = "https?:\\/\\/((25[0-5]|(2[0-4]|1\\d|[1-9]|)\\d)\\.?\\b){4}"
IP_ADDRES_REGEX = "((25[0-5]|(2[0-4]|1\\d|[1-9]|)\\d)\\.?\\b){4}"
PORT_REGEX = ":\\d{1,5}"

# name of the font for tkinter to use in all widgets
# This may not be the solution for the fontconfig error on the newer Linux systems but it should stop tkinter
# from trying to use some other fonts.
# See #92174 for the discussion.
FONT_NAME = "TkDefaultFont"


def center(win):
    """
    centers a tkinter window
    :param win: the main window or Toplevel window to center
    """
    win.update_idletasks()
    width = win.winfo_width()
    frm_width = win.winfo_rootx() - win.winfo_x()
    win_width = width + 2 * frm_width
    height = win.winfo_height()
    titlebar_height = win.winfo_rooty() - win.winfo_y()
    win_height = height + titlebar_height + frm_width
    x = win.winfo_screenwidth() // 2 - win_width // 2
    y = win.winfo_screenheight() // 2 - win_height // 2
    win.geometry('{}x{}+{}+{}'.format(width, height, x, y))
    win.deiconify()


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
    SSDP_HEADER_MIPAS = "mipas"

    MULTICAST_SSDP_PORT = 1900

    # time for redrawing all widgets in milliseconds
    UPDATE_TIME_MS = 100

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

        center(self.root)

        # get font object from its name
        self.main_font = font.nametofont(FONT_NAME)
        self.main_font.actual()
        # set this font as default for all tkinter widgets
        self.root.option_add("*Font", self.main_font)

        # configure ttk to use this font for all widgets (main button) as well
        s = ttk.Style()
        s.configure('.', font=self.main_font)

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

        # add main revealer table
        self.main_table = RevealerTable(mainframe, col=0, row=1, height=300, left_click_url_func=self.open_link,
                                        settings_func=self.change_ip_click,
                                        properties_view_func=self.view_prop,
                                        os_main_root=os.path.dirname(__file__),
                                        font_name=FONT_NAME)

        # configure paddings for the main frame
        for child in mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        # store event for using in clicking callbacks
        self.event = None

        # flag indicating that we are in the process
        self.window_updating = False

        # prepare notify socket for correct working
        self.sock_notify = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock_notify.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock_notify.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
        try:
            self.sock_notify.bind(('', self.MULTICAST_SSDP_PORT))

            init_ok = True
        except OSError:
            # we can't bind to this port number (it may be already taken)
            # create window with closing information
            mb.showerror(
                "Error",
                "\nSSDP port (" + str(self.MULTICAST_SSDP_PORT) + ") is already in use.",
                parent=self.root
            )
            # close notify socket
            self.sock_notify.close()
            self.root.destroy()
            init_ok = False

        if init_ok:
            self.info = ""

            # thread with the adding new rows methods
            self._update_table_thread = ParseDevicesThread()
            self._update_table_thread.start()
            # ssdp search thread
            self._ssdp_search_thread = ProcessThread()
            self._ssdp_search_thread.start()

            self._ssdp_threads = SSDPSearchThread()

            # legacy search thread
            self._old_search_thread = ProcessThread()
            self._old_search_thread.start()
            # thread for listening notify
            self._notify_search_thread = ProcessThread()
            self._notify_search_thread.start()

            # flag of the GUI destroying, is set than user wants to close the window
            self._destroy_flag = threading.Event()
            # flag of the search in progress
            self._in_process = threading.Event()
            # thread safe event to indicate that we need to update main table one time after search is ended
            self._in_process_after = threading.Event()
            # flag of the MIPAS in progress
            self._changing_settings = threading.Event()

            # flag indicating that main button state was changed for some process
            self.buttons_state_changed = False
            # flag indicating that table buttons states were changed for MIPAS
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
        if not self._destroy_flag.is_set():
            self.window_updating = True
            self.root.after(self.UPDATE_TIME_MS, self.update_window)
        else:
            self.window_updating = False

    def update_main_table(self):
        """
        Method for updating main table with current lists of the devices.

        :return:
        """

        if self._in_process.is_set() or not self._update_table_thread.empty() or self._ssdp_threads.in_process():
            self.main_table.update_with_rewriting()
            self.table_buttons_state_changed = True
            self._in_process_after.set()
        elif self._in_process_after.is_set():
            self._in_process_after.clear()
            self.main_table.update_with_rewriting()
            self.table_buttons_state_changed = True
        return

    def update_buttons(self):
        if self._in_process.is_set() or not self._update_table_thread.empty() or self._ssdp_threads.in_process():
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
        if self._in_process.is_set() or self._ssdp_threads.in_process():
            self.table_buttons_state_changed = True
        elif self._changing_settings.is_set():
            self.table_buttons_state_changed = True
            self.main_table.disable_all_buttons()
        elif self.table_buttons_state_changed:
            self.table_buttons_state_changed = False
            self.main_table.enable_all_buttons()

    def on_closing(self):
        """
        Method to be called on X button to close the application.
        :return:
        """

        # create window with closing information
        popup = Toplevel()
        # TODO: do we need this _ X for this window ?
        # popup.overrideredirect(True)
        popup.grab_set()
        # add revealer icon
        try:
            popup.iconphoto(False, PhotoImage(file=os.path.join(os.path.dirname(__file__),
                                                                "resources/appicon.png")))
        except Exception:
            pass

        popup_label = Label(popup, text="Revealer is closing. Please wait, it may take some time...")
        popup_label.grid(column=0, row=0, sticky="news")
        popup_label.grid_configure(padx=15, pady=15)
        # center this window
        center(popup)
        # update this window
        popup.update()
        self.root.update_idletasks()
        # popup.resizable(False, False)

        # set destroying flag
        self._destroy_flag.set()
        # close all threads first
        self._update_table_thread.stop_thread()
        self._ssdp_search_thread.stop_thread()
        self._old_search_thread.stop_thread()
        self._notify_search_thread.stop_thread()

        self._ssdp_threads.stop_all()

        # wait till all threads are stopped
        while self._update_table_thread.task_in_process() or \
                self._ssdp_search_thread.task_in_process() or \
                self._old_search_thread.task_in_process() or \
                self._notify_search_thread.task_in_process():
            pass

        # close notify socket
        self.sock_notify.close()

        # wait till we stops updating table here for not disturbing tkinter
        if self.window_updating:
            log.info("We are updating the window so please wait...")
            self.root.after(self.UPDATE_TIME_MS, self.destroy_after)

    def destroy_after(self):
        """
        After callback for destroying everything after our main updating after-method finished its work.

        :return:
        """

        if not self.window_updating:
            # and only after all of this - kill the app
            log.info("Now the window can be closed. Bye.")
            self.root.destroy()
        else:
            log.info("We are updating the window so please wait...")
            self.root.after(self.UPDATE_TIME_MS, self.destroy_after)

    def print_i(self, string):
        if len(self.info) > 0:
            self.info += "\n\n"
        self.info += string

    def show_info(self):
        """
        Method for catching exceptions and showing them in separate windows.

        :return:
        """
        if len(self.info) > 0 and not self._destroy_flag.is_set():
            mb.showerror('Error', self.info)

    def start_thread_search(self):

        # remove everything from our table
        self.main_table.delete_all_rows()
        # and delete all devices from the device list of the table
        self.main_table.device_list.clear_all()

        # information about this search
        self.info = ""

        # start thread searches
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
            if prop_dict['friendlyName'] == "Not provided":
                name = prop_dict['ssdp_server']
            else:
                name = prop_dict['friendlyName']
            PropDialog(name, prop_dict, link, parent=self.root)
        except KeyError:
            try:
                # if we have not local SSDP device
                name = prop_dict['server']
                PropDialog(name, prop_dict, link, parent=self.root)
            except KeyError:
                log.debug('No properties for this device')
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
                        log.debug('No properties for this device')
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
                        log.debug('No properties for this device')
                        pass

    def open_link(self, event=None):
        if event is not None:
            self.event = event
        label = self.event.widget  # get the label widget

        if label.winfo_class() == 'Label':
            if hasattr(label, 'link') and hasattr(label, 'tag'):
                if (label.tag == RevealerDeviceTag.LOCAL or label.tag == RevealerDeviceTag.OLD_LOCAL) and \
                        label['foreground'] == "blue":
                    wb.open_new_tab(label.link)  # open the link in a browser tab
                else:
                    log.info(f"Can't open {label.link} link.")

    def _listen_and_capture_returned_responses_url(self, sock: socket.socket, timer_stop_event):
        while not self._destroy_flag.is_set() and not timer_stop_event.is_set():
            try:
                while not self._destroy_flag.is_set() and not timer_stop_event.is_set():
                    data, addr = sock.recvfrom(8192)
                    data_dict = self.parse_ssdp_data(data.decode('utf-8'), addr)
                    # if we have not received this location before
                    if data_dict["server"] != "":
                        self._update_table_thread.add_task(self.add_new_item_task, data_dict, addr)
            except socket.timeout:
                pass
            except OSError:
                break

        sock.close()

    def ssdp_search_task(self):

        try:
            if not self._destroy_flag.is_set():
                self._in_process.set()
                self._in_process_after.set()
            else:
                return

            notify_started = False

            adapters = ifaddr.get_adapters()

            self._ssdp_threads.delete_all()
            self._ssdp_threads.add_adapters(adapters)

            index = 0

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
                        index += 1
                        continue

                    # if ip.ip is suitable for m-search - try to listen for notify messages also
                    # just ONE time
                    if not notify_started:
                        # set notify flag to make that process know that it need to listen answers
                        self._ssdp_threads.start_notify()
                        # we need to wait a little bit for notify listen to start on
                        # this ip for correct answers receiving
                        # See #89128.
                        self._notify_search_thread.add_task(self.listen_notify_task, ip.ip)
                        notify_started = True
                        time.sleep(0.05)

                    # adding search task for this ip on this adapter
                    self._ssdp_threads[index].start()
                    self._ssdp_threads[index].add_task(self.ssdp_search_adapter_task, sock,
                                                       self._ssdp_threads[index].stop_flag)

                    index += 1

            self._in_process.clear()
            # set notify flag to false so notify thread will stop when all ssdp searches are finished
            self._ssdp_threads.stop_notify()

        except Exception:
            except_info = traceback.format_exc()
            self.print_i(f"Unhandled exception occurred while performing SSDP search:\n{except_info}")

        # show info from search if we had some important information (exceptions with errors)
        if not self._destroy_flag.is_set():
            self.show_info()

        return

    def ssdp_search_adapter_task(self, sock, timer_stop_event):
        # M-Search message body
        message = \
            'M-SEARCH * HTTP/1.1\r\n' \
            'HOST:239.255.255.250:1900\r\n' \
            'ST:upnp:rootdevice\r\n' \
            'MX:2\r\n' \
            'MAN:"ssdp:discover"\r\n' \
            '\r\n'

        # set timeout
        sock.settimeout(0.05)
        timer_stop_event.clear()
        try:
            sock.sendto(message.encode('utf-8'), ("239.255.255.250", 1900))
            self._listen_and_capture_returned_responses_url(sock, timer_stop_event)
        except OSError:
            pass

    def _get_uuid_of_found(self, data_dict):
        """
        Check if this device is our enhanced device with correct version.

        :return:
        """

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
                elif current_version_array[0] == version_with_settings_array[0]:
                    if current_version_array[1] < version_with_settings_array[1]:
                        uuid = ""
                    elif current_version_array[1] == version_with_settings_array[1]:
                        if current_version_array[2] < version_with_settings_array[2]:
                            uuid = ""

        elif data_dict['mipas'] == "True":
            uuid = data_dict["uuid"]

        else:
            uuid = None

        return uuid

    def add_new_item_task(self, data_dict, addr, notify_flag=False):

        try:
            xml_dict = self.parse_upnp_xml(data_dict["location"])

            uuid = self._get_uuid_of_found(data_dict)

            if uuid is None and notify_flag:
                # we don't need not our device from notify
                return

            if xml_dict is not None:
                # append all datadict field to xml_dict
                for name in data_dict:
                    xml_dict[name] = data_dict[name]
                # check that we have our url with correct format
                try:
                    if xml_dict["presentationURL"] is None:
                        link = data_dict["location_url"]
                        xml_dict["presentationURL"] = '-'
                    elif xml_dict["presentationURL"][0:4] != "http":
                        link = data_dict["location_url"] + xml_dict["presentationURL"]
                    else:
                        # from the XML-description we should get relative URL but if we have absolute - use absolute
                        link = xml_dict["presentationURL"]
                except KeyError:
                    xml_dict["presentationURL"] = '-'
                    link = addr[0]

                # add version and server name from ssdp dict
                xml_dict["version"] = data_dict["version"]
                xml_dict["ssdp_server"] = data_dict["server"]

                # try to avoid all None fields in the xml data
                for field in xml_dict:
                    if xml_dict[field] is None:
                        xml_dict[field] = "Not provided"

                # check friendlyName field
                if "friendlyName" not in xml_dict or xml_dict["friendlyName"] == "Not provided":
                    device_name = xml_dict["ssdp_server"]
                else:
                    device_name = xml_dict["friendlyName"]

                if not self._destroy_flag.is_set():
                    with self.main_table.lock:
                        self.main_table.add_row_ssdp_item(device_name,
                                                          link, data_dict["ssdp_url"], uuid, xml_dict,
                                                          tag=RevealerDeviceTag.LOCAL)
            else:
                if not self._destroy_flag.is_set():
                    with self.main_table.lock:
                        self.main_table.add_row_ssdp_item(data_dict["server"],
                                                          data_dict["ssdp_url"], data_dict["ssdp_url"],
                                                          uuid, data_dict, tag=RevealerDeviceTag.NOT_LOCAL)
        except Exception:
            except_info = traceback.format_exc()
            self.print_i(f"Error while trying to add new device {addr} with data_dict {data_dict} to the table:\n"
                         f"{except_info}")

    def socket_notify_reinit(self):
        # close notify socket
        self.sock_notify.close()

        # prepare notify socket for correct working
        self.sock_notify = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock_notify.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock_notify.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
        try:
            self.sock_notify.bind(('', self.MULTICAST_SSDP_PORT))

        except OSError:
            # we can't bind to this port number (it may be already taken)
            # create window with closing information
            mb.showerror(
                "Error",
                "\nSSDP port (" + str(self.MULTICAST_SSDP_PORT) + ") is already in use.",
                parent=self.root
            )
            # close notify socket
            self.sock_notify.close()
            self.root.destroy()

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

        self.sock_notify.settimeout(0.1)

        while self._ssdp_threads.in_process() and not self._destroy_flag.is_set():
            # listen and capture returned responses
            try:
                while self._ssdp_threads.in_process() and not self._destroy_flag.is_set():
                    data, addr = self.sock_notify.recvfrom(8192)
                    data_strings = data.decode('utf-8').split('\r\n')

                    if data_strings[0] == 'NOTIFY * HTTP/1.1':
                        data_dict = self.parse_ssdp_data(data.decode('utf-8'), addr)
                        # NOTIFY flag at the end of the arguments is set to False since we don't want to filter NOTIFY
                        # answers. #92687
                        self._update_table_thread.add_task(self.add_new_item_task, data_dict, addr, False)

            except socket.timeout:
                pass
            except OSError:
                break

    def _parse_ssdp_header_server(self, string, ssdp_dict) -> None:
        """
        Correct format for SERVER header is:
            <OS>/<OS version> UPnP/<version of UPnP supported> <product>/<product version>

        All fields should be filled according to HTTP/1.1 “product tokens”.

        For example, “SERVER: unix/5.1 UPnP/2.0 MyProduct/1.0”

        Note: whitespaces are used as separator so should not be used in OS / product strings but if some device has
        additional whitespaces in its product tokens revealer should try and parse them as well with logging about that.

        :param string: str
           String after SERVER header.
        :param ssdp_dict: dict
           Dict with SSDP properties of this device to be filled with parsed information.
        :return:
        """
        warning_line = ''

        words_string = string.split(' ')
        # check that format is correct
        if len(words_string) != 3:
            warning_line += "SERVER header line with incorrect format: '" +\
                            string + "'. Whitespaces shouldn't be used in the OS and product names."

            # try to find UPnP field
            index_upnp = string.index("UPnP/")
            if index_upnp < 0:
                warning_line += "Can't parse SERVER header line without UPnP field at all: '" +\
                                string + "'."
                os_version_words = ["Not provided", "Not provided"]
                server_version_words = ["Not provided", "Not provided"]
            else:
                os_fields = string[0:index_upnp]
                os_version_words = os_fields.split('/')

                product_fields = string[index_upnp + 1 + string[index_upnp:].index(" "):]
                server_version_words = product_fields.split('/')

        else:
            os_version = words_string[0]
            os_version_words = os_version.split('/')
            # TODO: check different lines (with trailing whitespaces and so on)
            server_version = words_string[len(words_string) - 1]  # last word after ' '
            server_version_words = server_version.split('/')

        if len(warning_line) > 0:
            print("Warning:", warning_line)

        try:
            ssdp_dict["server"] = server_version_words[0]
        except IndexError:
            ssdp_dict["server"] = "Not provided"
        try:
            ssdp_dict["version"] = server_version_words[1]
        except IndexError:
            ssdp_dict["version"] = "Not provided"

        try:
            ssdp_dict["os"] = os_version_words[0]
        except IndexError:
            ssdp_dict["os"] = "Not provided"
        try:
            ssdp_dict["os_version"] = os_version_words[1]
        except IndexError:
            ssdp_dict["os_version"] = "Not provided"

    @staticmethod
    def _parse_location_url(string):
        m = re.search(URL_REGEX_PORT, string)

        try:
            url_raw = m.group()
            rest_data = string[len(url_raw):]
            ip_address = (re.search(IP_ADDRES_REGEX, url_raw)).group()
            port = (re.search(PORT_REGEX, url_raw)).group()
            return ip_address, port[1::1], rest_data
        except AttributeError:
            # try get url without port
            m = re.search(URL_REGEX_WITHOUT_PORT, string)
            try:
                url_raw = m.group()
                rest_data = string[len(url_raw):]
                ip_address = (re.search(IP_ADDRES_REGEX, url_raw)).group()
                return ip_address, None, rest_data
            except AttributeError:
                return None, None, string

    def _parse_ssdp_header_location(self, string, ssdp_dict, addr) -> None:
        # get only field value:

        field_name = re.match("location:\\s*", string.lower()).group()
        value_string = string[len(field_name):]

        ip_address, port, xml_raw = self._parse_location_url(value_string)

        if ip_address is not None and port is not None:
            # we have correct absolute location - save it as location
            ssdp_dict["location"] = value_string
        elif ip_address is not None and port is None:
            # if we don't have port specification
            ssdp_dict['location'] = 'http://' + ip_address + ":80" + xml_raw
        else:
            # if we are here it means we have an invalid LOCATION URL -
            # relative one but UPnP standards require an absolute URL.
            # See https://openconnectivity.org/upnp-specs/UPnP-arch-DeviceArchitecture-v2.0-20200417.pdf
            # on pages 29 and 41 for LOCATION header format
            #
            # Nevertheless we are trying to get xml-file for this devices with address
            ssdp_dict['location'] = 'http://' + addr[0] + ":80" + xml_raw

        ssdp_dict["ssdp_url"] = addr[0]
        ssdp_dict["location_url"] = re.match(URL_REGEX_PORT, value_string.lower()).group()

    def _parse_ssdp_header_usn(self, string, ssdp_dict, addr) -> None:
        words_string = string.split(':')  # do this again for symmetry
        try:
            ssdp_dict["uuid"] = words_string[2]
        except IndexError:
            except_info = traceback.format_exc()
            self.print_i(f"USN of {addr} has incorrect format: {string}. It should be:\n"
                         f"USN: uuid:00000000-0000-0000-0000-000000000000::<device-type>."
                         f"\n{except_info}")

    def parse_ssdp_data(self, ssdp_data, addr):
        ssdp_dict = {"server": "Not provided", "version": "Not provided", "location": "Not provided",
                     "ssdp_url": "Not provided", "uuid": "Not provided", "location_url": "Not provided",
                     "os": "Not provided", "os_version": "Not provided", "mipas": "Not provided"}
        ssdp_strings = ssdp_data.split("\r\n")

        try:
            for string in ssdp_strings:
                if string[0:3].lower() != Revealer2.SSDP_HEADER_HTTP:
                    words_string = string.split(':')

                    if words_string[0].lower() \
                            == Revealer2.SSDP_HEADER_SERVER:  # format: SERVER: lwIP/1.4.1 UPnP/2.0 8SMC5-USB/4.7.7
                        # remove header from string
                        string = string[len(Revealer2.SSDP_HEADER_SERVER)+1:]
                        if len(string) > 0 and string[0] == ' ':
                            string = string[1:]
                        if len(string) > 0:
                            self._parse_ssdp_header_server(string, ssdp_dict)
                    elif words_string[0].lower() == \
                            Revealer2.SSDP_HEADER_LOCATION:  # format: LOCATION: http://172.16.130.67:80/Basic_info.xml
                        self._parse_ssdp_header_location(string, ssdp_dict, addr)
                    elif words_string[0].lower() == \
                            Revealer2.SSDP_HEADER_USN:
                        # USN: uuid:40001d0a-0000-0000-8e31-4010900b00c8::upnp:rootdevice
                        self._parse_ssdp_header_usn(string, ssdp_dict, addr)
                    elif words_string[0].lower() == \
                            Revealer2.SSDP_HEADER_MIPAS:
                        # MIPAS: - our special field to identifty that this device
                        # supports network settings changing via multicast
                        ssdp_dict["mipas"] = "True"
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

            tree = ET.fromstring(response)

            for child in tree:
                tag_array = child.tag.split('}')
                tag_name = tag_array[len(tag_array) - 1]
                xml_dict[tag_name] = child.text

                for grandchild in child:
                    tag_array = grandchild.tag.split('}')
                    tag_name = tag_array[len(tag_array) - 1]
                    xml_dict[tag_name] = grandchild.text

            return xml_dict

        except Exception as err:
            print("Exception for xml_dict", url, err)
            return None

    def change_ip_multicast(self, uuid, settings_dict):

        # delete any info from previous process
        self.info = ""

        # start process for changing settings in another thread
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
                "Success.\nNew settings were applied.\nPlease refresh the list of "
                "the devices by clicking the Search button.",
                parent=self.root
            )
        else:
            mb.showerror(
                "Change settings...",
                "Error.\nSomething went wrong while setting the new settings."
                "\nPlease check the values inserted and try again.",
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

            # here it is important to avoid getting an old notify reply so we need to reopen notify socket
            self.socket_notify_reinit()

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

            MIPAS: <password>;<dhcp usage flag(0/1)>;<ip-address>;<subnet mask>;<gateway address>;\r\n

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
                if self._destroy_flag.is_set():
                    break
                if len(devices) > 0:
                    break
                self._change_ips_of_adapter(adapter, message, devices, uuid)

            if not self._destroy_flag.is_set():
                self._show_change_settings_info(devices)

            self._changing_settings.clear()
        except Exception:
            except_info = traceback.format_exc()
            self.print_i(f"Unhandled error while setting device network settings:\n{except_info}")

        # show window with errors if there were any
        if not self._destroy_flag.is_set():
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
                log.error(f"Errors in inserted values for changing network settings process: {dialog.result}")

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

    USER_NOTE_TEXT = "\nNote: this is a service fallback interface for device network access recovery." \
                     "\nClick on URL for recommended network administration page if active."

    def __init__(self, title, device, uuid,
                 initialvalue=None,
                 parent=None):

        self.main_font = font.nametofont(FONT_NAME)
        self.main_font.actual()

        self.device = device
        self.uuid = uuid

        self.initialvalue = initialvalue

        self.entry_ip = None
        self.entry_mask = None
        self.entry_password = None

        self.entry_gateway = None

        self.checkbox_dhcp = None
        self.dhcp = IntVar()

        self.note_label = None

        # for macos we may want to change this color to white or just default system color
        self.text_color = "SystemButtonText"

        sd.Dialog.__init__(self, parent, title)

    def entry_click(self, event):
        entry_widget = event.widget

        if entry_widget.default:
            entry_widget.default = False
            entry_widget.delete(0, 'end')
            # try to change color for macos
            try:
                entry_widget.configure(fg=self.text_color)
            except TclError:
                entry_widget.configure(fg=DEFAULT_TEXT_COLOR)
                pass

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

        # add revealer icon
        try:
            self.iconphoto(False, PhotoImage(file=os.path.join(os.path.dirname(__file__),
                                                               "resources/appicon.png")))
        except Exception:
            pass

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

        # try to change foreground color for macos
        try:
            frame = LabelFrame(master, text="Network settings", fg=self.text_color,
                               font=(self.main_font.name, self.main_font.actual()['size'], 'bold'))
        except TclError:
            frame = LabelFrame(master, text="Network settings",
                               font=(self.main_font.name, self.main_font.actual()['size'], 'bold'))

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
        self.entry_gateway.bind("<FocusIn>", self.entry_click)
        self.entry_gateway.bind("<Button-1>", self.entry_click)
        self.entry_gateway.bind("<FocusOut>", self.entry_leave)
        self.entry_gateway.default = True

        # add note about settings for the user
        note_frame = Frame(master)
        note_frame.grid(row=3, column=0, sticky='news')

        self.note_label = Label(note_frame, text=self.USER_NOTE_TEXT, justify=LEFT,
                                font=(self.main_font.name, self.main_font.actual()['size'], 'italic'),
                                wraplength=100)
        self.note_label.grid(column=0, row=0, padx=5, sticky='we')

        self.update()
        self.update_idletasks()

        # self.minsize(width=max(device_frame.winfo_width(), frame.winfo_width(), note_frame.winfo_width()) + 30,
        #             height=400)

        self.resizable(False, False)

        note_frame.bind('<Configure>', self._configure_canvas)

        return self.entry_password

    def _configure_canvas(self, event):
        self.note_label.configure(wraplength=event.widget.winfo_width())

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
                           " a number from 0 to 255." \
                           "\nExample: 192.168.1.1."
        if self.check_format(result_ip['netmask'], self.NET_MASK_RE):
            if len(warning_msg) > 0:
                warning_msg += "\n\n"
            warning_msg += "Network Mask format is incorrect.\nMost likely you need Network Mask 255.255.0.0 or " \
                           "255.255.255.0.\nIf these aren't the mask you need, check " \
                           "possible network mask values " \
                           "on the Internet and insert it in the format of #.#.#.#."
        if result_ip['gateway'] != '' and self.check_format(result_ip['gateway'], self.IP_ADDRESS_RE):
            if len(warning_msg) > 0:
                warning_msg += "\n\n"
            warning_msg += "Gateway Address format is incorrect.\nRequired format: #.#.#.#, where # stands for" \
                           " a number from 0 to 255." \
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
                "\nThe length of the password of this device can be 20 symbols or less.",
                parent=self
            )
            return 0

        if result_ip['dhcp'] == 0 and (result_ip['ip'] == '' or result_ip['netmask'] == ''):
            mb.showwarning(
                "Warning",
                "\nPlease insert an IP address and a Network Mask or choose the DHCP mode "
                "for the network configuration.",
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

        self.main_font = font.nametofont(FONT_NAME)
        self.main_font.actual()

        self.dict = properties_dict

        self.labels_dict = {'friendlyName': {'name': 'Friendly name', 'row': 0},
                            'manufacturer': {'name': 'Manufacturer', 'row': 1},
                            'manufacturerURL': {'name': 'Manufacturer URL', 'row': 2},
                            'modelDescription': {'name': 'Model description', 'row': 3},
                            'modelName': {'name': 'Model name', 'row': 4},
                            'modelNumber': {'name': 'Model number', 'row': 5},
                            'modelURL': {'name': 'Model URL', 'row': 6},
                            'serialNumber': {'name': 'Serial number', 'row': 7},
                            'UDN': {'name': 'UDN', 'row': 8},
                            'presentationURL': {'name': 'Presentation URL', 'row': 9},
                            'server': {'name': 'Product', 'row': 32},
                            'uuid': {'name': 'UUID', 'row': 34},
                            'version': {'name': 'Product version', 'row': 33},
                            'ssdp_url': {'name': 'IP', 'row': 35},
                            'os': {'name': 'OS', 'row': 30},
                            'os_version': {'name': 'OS version', 'row': 31},
                            'location': {'name': 'Location', 'row': 36}}

        # try to use mac os specific cursor - if exception is raised we are not on mac os and should use default
        self.pointer_cursor = CURSOR_POINTER_MACOS
        try:
            test_label = Label(parent, text='', cursor=self.pointer_cursor)
            test_label.destroy()
            self.text_color = "SystemButtonText"
        except TclError:
            self.pointer_cursor = CURSOR_POINTER
            self.text_color = DEFAULT_TEXT_COLOR

        sd.Dialog.__init__(self, parent, device_name)

    def destroy(self):
        sd.Dialog.destroy(self)

    def body(self, master):

        # add revealer icon
        try:
            self.iconphoto(False, PhotoImage(file=os.path.join(os.path.dirname(__file__),
                                                               "resources/appicon.png")))
        except Exception:
            pass

        label_count = 0

        for name in self.dict:

            font_style = ''
            cursor = ''
            if self.dict[name] is not None:
                try:
                    text_color = self.text_color
                    label_name = self.labels_dict[name]['name']
                    row_number = self.labels_dict[name]['row']
                    if row_number >= self.labels_dict['server']['row']:
                        ttk.Separator(master, orient='horizontal').grid(column=0, row=29, pady=5, sticky='news')
                        ttk.Separator(master, orient='horizontal').grid(column=1, row=29, pady=5, sticky='news')
                    Label(master, text=label_name + ": ", justify=LEFT, fg=text_color,
                          font=(self.main_font.name, self.main_font.actual()['size'],
                                'bold')).grid(column=0, row=row_number, padx=5, sticky='w')
                    label_count += 1
                    if name == 'presentationURL' and self.dict[name] != '-':
                        text_color = "blue"
                        Label(master, text=self.url, justify=LEFT, cursor=self.pointer_cursor, fg=text_color,
                              font=(self.main_font.name, self.main_font.actual()['size'], 'underline')).grid(
                            column=1, row=row_number, padx=5, sticky='w')
                        label_count += 1
                    elif name == 'presentationURL' and self.dict[name] == '-':
                        Label(master, text='Not provided', justify=LEFT, fg=text_color,
                              font=(self.main_font.name, self.main_font.actual()['size'], 'italic')).grid(
                            column=1, row=row_number, padx=5, sticky='w')
                        label_count += 1
                    else:
                        if self.dict[name][0:4] == "http":
                            font_style = 'underline'
                            cursor = self.pointer_cursor
                            text_color = "blue"
                        elif self.dict[name] == "Not provided":
                            font_style = 'italic'
                        Label(master, text=self.dict[name], justify=LEFT, cursor=cursor, fg=text_color,
                              font=(self.main_font.name, self.main_font.actual()['size'], font_style)).grid(
                            column=1, row=row_number, padx=5, sticky='w')
                        label_count += 1
                except KeyError:
                    pass

        self.bind("<Button-1>", self.open_link)

        self.update()
        self.update_idletasks()

        self.resizable(False, False)

        return self

    def buttonbox(self):
        """add standard button box.

        override if you do not want the standard buttons
        """

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
        except TclError:
            pass


if __name__ == '__main__':
    print("Starting revealer version " + Version.full + ".")

    app = Revealer2()
    try:
        app.root.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.root.after(app.UPDATE_TIME_MS, app.update_window)
        app.root.mainloop()
    except TclError:
        pass

    del app

    print("End.")
