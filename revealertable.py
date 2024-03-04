import os
from tkinter import ttk, Canvas, HORIZONTAL, VERTICAL, Frame, TclError, Label, font, Button, PhotoImage
import threading
from idlelib.tooltip import Hovertip

import time

import logging as log
from revealerdevice import RevealerDeviceTag, RevealerDeviceType, RevealerDeviceList, RevealerDeviceRow

DEFAULT_TEXT_COLOR = "black"
CURSOR_POINTER = "hand2"
CURSOR_POINTER_MACOS = "pointinghand"
DEFAULT_BG_COLOR = "white"


class AutoScrollbar(ttk.Scrollbar):
    # a scrollbar that hides itself if it's not needed.  only
    # works if you use the grid geometry manager.
    def __init__(self, parent, **kw):
        ttk.Scrollbar.__init__(self, parent, **kw)

        self.column = None
        self.row = None
        self.active = False

    def set(self, lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            # grid_remove is currently missing from Tkinter!
            self.grid_forget()
            self.active = False
        else:
            if self.column is not None and self.row is not None:
                if self.cget("orient") == HORIZONTAL:
                    self.grid(column=self.column, row=self.row, sticky='we')
                    self.active = True
                else:
                    self.grid(column=self.column, row=self.row, sticky='ns')
                    self.active = True
            else:
                self.grid_forget()
                self.active = False

        ttk.Scrollbar.set(self, lo, hi)

    def grid(self, **kw):
        try:
            self.column = kw['column']
            self.row = kw['row']
        except KeyError:
            pass

        ttk.Scrollbar.grid(self, **kw)

    def pack(self, **kw):
        raise TclError

    def place(self, **kw):
        raise TclError


class VerticalScrolledFrame(Frame):
    def __init__(self, parent, column, row, *args, **kw):
        Frame.__init__(self, parent, *args, **kw)

        self.grid(column=column, row=row, sticky='news')

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.propagate(False)

        # Create a canvas object and a vertical scrollbar for scrolling it.
        self.vscrollbar = AutoScrollbar(self, orient=VERTICAL)
        self.vscrollbar.grid(column=1, row=0, sticky='ns')
        self.canvas = Canvas(self, bd=0, highlightthickness=0,
                             width=200, height=300,
                             yscrollcommand=self.vscrollbar.set, background=DEFAULT_BG_COLOR)
        self.canvas.grid(column=0, row=0, sticky='news')
        self.vscrollbar.config(command=self.canvas.yview)

        self.canvas.grid_rowconfigure(0, weight=1)
        self.canvas.grid_columnconfigure(0, weight=1)

        # Reset the view
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

        self.canvas.propagate(False)

        # Create a frame inside the canvas which will be scrolled with it.
        self.interior = Frame(self.canvas)
        self.interior.grid(column=0, row=0, sticky='news')

        self.interior.propagate(False)

        self.interior.bind('<Configure>', self._configure_interior)
        self.interior_id = self.canvas.create_window(0, 0, window=self.interior, anchor="nw")

        self.canvas.bind('<Configure>', self._configure_canvas)

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        # in Unix systems we need to use Button-4 and Button-5 as MouseWheel indication
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        # only if scrollbar is active
        if self.vscrollbar.active:
            # in Unix systems we need to use Button-4 and Button-5 as MouseWheel indication
            if event.num == 4:
                # up
                self.canvas.yview_scroll(int(-1), "units")
            elif event.num == 5:
                # down
                self.canvas.yview_scroll(int(1), "units")
            else:
                # auto calculate for mouse wheel in windows
                if event.delta >= 120 or event.delta <= -120:
                    self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                else:
                    self.canvas.yview_scroll(int(event.delta), "units")

    def _configure_interior(self, event):
        # Update the scrollbars to match the size of the inner frame.
        size = (self.interior.winfo_reqwidth(), self.interior.winfo_reqheight())
        self.canvas.config(scrollregion=(0, 0, size[0], size[1]))
        if self.interior.winfo_reqwidth() != self.canvas.winfo_width():
            # Update the canvas's width to fit the inner frame.
            self.canvas.config(width=self.interior.winfo_reqwidth())

    def _configure_canvas(self, event):
        if self.interior.winfo_width() != self.canvas.winfo_width():
            # Update the inner frame's width to fill the canvas.
            self.canvas.itemconfigure(self.interior_id, width=self.canvas.winfo_width())


class RevealerTable:
    """
    Class for creating our table with structure:
      ____________________________________________
     |_____SSDP_Devices_____|________URL_______|__|
     |                                            |
     |                                            |
     |                                            |
     |____________________________________________|

    """

    EVEN_ROW_COLOR = "#eAeFeF"
    # EVEN_ROW_COLOR = "yellow"
    HEADER_COLOR = "#ced0d0"

    HEADER_TAG = "header"
    ADDITIONAL_HEADER_TAG = "header_add"

    BLANK_LINE_TAG = "blank"

    # this value minus 3 defines max ssdp devices counts to be listed without moving the legacy table
    LEGACY_HEADER_ROW = 1000

    lock = threading.Lock()

    def __init__(self, master, col, row, height, left_click_url_func=None, right_click_func=None, settings_func=None,
                 properties_view_func=None, os_main_root=None, font_name='TkTextFont'):
        self.great_table = None

        self.main_table = self.create_table(master, col, row, height)
        self.left_click_func = left_click_url_func
        self.right_click_func = right_click_func
        self.settings_func = settings_func
        self.properties_view_func = properties_view_func

        self.main_font = font.nametofont(font_name)
        self.main_font.actual()

        self.col = col
        self.row = row

        # last added row
        self.last_row = 1

        # exist at least one legacy device
        self.legacy_last_row = 0
        self.legacy_header_row = 0

        self.device_list = RevealerDeviceList()

        # save path root to the main.py if it is provided - if no: just save path to this file
        if os_main_root is not None:
            self.os_main_root = os_main_root
        else:
            self.os_main_root = os.path.dirname(__file__)

        # try to use mac os specific cursor - if exception is raised we are not on mac os and should use default
        self.pointer_cursor = CURSOR_POINTER_MACOS
        try:
            test_label = Label(self.main_table, text='', cursor=self.pointer_cursor)
            test_label.destroy()
        except TclError:
            self.pointer_cursor = CURSOR_POINTER

        self.ssdp_rows = []
        self.legacy_rows = []

    def create_table(self, master, col, row, height):

        # prepare frame for using with scrollbar
        self.great_table = VerticalScrolledFrame(master, column=col, row=row, borderwidth=1, relief="solid",
                                                 background=DEFAULT_BG_COLOR,
                                                 height=height, width=500)

        self.legacy_header_row = self.LEGACY_HEADER_ROW

        # get object of the real frame to fill in with found devices
        new_table = self.great_table.interior

        # add headers
        header_1 = Label(new_table, text="SSDP Devices", anchor="center", background=self.HEADER_COLOR,
                         fg=DEFAULT_TEXT_COLOR)
        header_1.grid(row=0, column=0, sticky="ew")
        header_1.tag = self.HEADER_TAG

        header_2 = ttk.Separator(new_table, takefocus=0, orient=VERTICAL)
        header_2.grid(row=0, column=1, sticky="news")
        header_2.tag = self.HEADER_TAG

        header_3 = Label(new_table, text="URL / IP", anchor="center", background=self.HEADER_COLOR, height=0,
                         fg=DEFAULT_TEXT_COLOR)
        header_3.grid(row=0, column=2, sticky="ew")
        header_3.tag = self.HEADER_TAG

        header_4 = ttk.Separator(new_table, takefocus=0, orient=VERTICAL)
        header_4.grid(row=0, column=3, sticky="news")
        header_4.tag = self.HEADER_TAG

        header_5 = Frame(new_table, background=self.HEADER_COLOR, width=21)
        header_5.grid(row=0, column=4, sticky="news")
        header_5.tag = self.HEADER_TAG

        # configure columns to expand and separate line column to not expand
        new_table.grid_columnconfigure(0, weight=1, minsize=200)
        new_table.grid_columnconfigure(1, weight=0)  # separator
        new_table.grid_columnconfigure(2, weight=1, minsize=200)
        new_table.grid_columnconfigure(3, weight=0)  # separator
        new_table.grid_columnconfigure(4, weight=0, minsize=21)  # settings button

        new_table.configure(background=DEFAULT_BG_COLOR)

        return new_table

    def disable_all_buttons(self):
        """
        Method for disabling all buttons in the table while settings changing or searching.

        :return:
        """

        for i in self.main_table.winfo_children():
            if hasattr(i, 'button_flag'):
                # disable all buttons
                if i.button_flag:
                    i.button.disable()

    def enable_all_buttons(self):
        """
        Method for disabling all buttons in the table while settings changing or searching.

        :return:
        """

        for i in self.main_table.winfo_children():
            if hasattr(i, 'button_flag'):
                # destroy all children which is not header
                if i.button_flag:
                    i.button.enable()

    def update(self):
        """
        Update table according to current state of the list

        :return:
        """

        # delete all rows
        # self.delete_all_rows()

        _start_time = time.time()

        old_widget_number = len(self.main_table.winfo_children())

        for i in self.main_table.winfo_children():
            if hasattr(i, 'tag'):
                # destroy all children which is not header
                if not i.tag == self.HEADER_TAG:
                    i.destroy_tag = '1'
            else:
                # and if does not have any tag at all
                i.destroy_tag = '1'

        # append ssdp devices
        for i in range(len(self.device_list.ssdp_devices)):
            self.add_ssdp_row(row=i + 1, device_row=self.device_list.ssdp_devices[i])

        if len(self.device_list.old_devices) > 0:
            self.add_legacy_headers(row=len(self.device_list.ssdp_devices) + 1)
            start_legacy_row = 4 + len(self.device_list.ssdp_devices)
            for i in range(len(self.device_list.old_devices)):
                self.add_legacy_row(row=i + start_legacy_row, device_row=self.device_list.old_devices[i])

        log.debug(f"old_widget_number = {old_widget_number}")
        log.debug(f"len(self.main_table.winfo_children()) = {len(self.main_table.winfo_children())}")

        _time = time.time()

        # self.delete_to_widget(old_widget_number)

        log.debug(f"len(self.main_table.winfo_children()) = {len(self.main_table.winfo_children())}."
                  f" Time = {time.time() - _start_time} secs. Other time = {time.time() - _time}")

    def update_with_rewriting(self):
        """
        Update main table with rewriting data in the labels and not rebuilding the whole table
        :return:
        """

        ssdp_shown = len(self.ssdp_rows)
        legacy_shown = len(self.legacy_rows)

        len_ssdp = len(self.device_list.ssdp_devices)
        len_legacy = len(self.device_list.old_devices)
        min_len = min(len_ssdp, len_legacy)

        # if no legacy devices were shown and now we have some - draw legacy headers
        # TODO: what if we have a lot of devices - we need to move all rows down
        if legacy_shown == 0 and len(self.device_list.old_devices) > 0:
            self.add_legacy_headers(row=self.LEGACY_HEADER_ROW)

        # do for every row from each list
        for i in range(min_len):
            # update this row in the ssdp list
            if i + 1 > ssdp_shown:
                self.add_ssdp_row(row=i + 1, device_row=self.device_list.ssdp_devices[i])

            else:
                device_info = self.device_list.ssdp_devices[i].get_dict()
                self.ssdp_row_reinit(device_widget=self.ssdp_rows[i][0], link_widget=self.ssdp_rows[i][1],
                                     button_widget=self.ssdp_rows[i][2], device_info=device_info)

            self.ssdp_rows[i][2].disable()

            # and in the legacy
            if i + 1 > legacy_shown:
                self.add_legacy_row(row=self.LEGACY_HEADER_ROW + i + 1 + 3, device_row=self.device_list.old_devices[i])

            else:
                # just update row info
                self.legacy_rows[i][0].configure(text=self.device_list.old_devices[i].name)
                self.legacy_rows[i][1].configure(text=self.device_list.old_devices[i].link)

            if i % 5 == 9:
                self.main_table.update()

        for i in range(min_len, min_len + max(0, len_legacy-min_len)):
            if i + 1 > legacy_shown:
                self.add_legacy_row(row=self.LEGACY_HEADER_ROW + i + 1 + 3, device_row=self.device_list.old_devices[i])

            else:
                # just update row info
                self.legacy_rows[i][0].configure(text=self.device_list.old_devices[i].name)
                self.legacy_rows[i][1].configure(text=self.device_list.old_devices[i].link)

            if i % 10 == 9:
                self.main_table.update()

        # update ssdp devices if its row was already in the list or add row
        for i in range(min_len, min_len + max(0, len_ssdp-min_len)):
            if i + 1 > ssdp_shown:
                self.add_ssdp_row(row=i + 1, device_row=self.device_list.ssdp_devices[i])

            else:
                device_info = self.device_list.ssdp_devices[i].get_dict()
                self.ssdp_row_reinit(device_widget=self.ssdp_rows[i][0], link_widget=self.ssdp_rows[i][1],
                                     button_widget=self.ssdp_rows[i][2], device_info=device_info)

            self.ssdp_rows[i][2].disable()

            if i % 10 == 9:
                self.main_table.update()

    def button_reinit(self, button, device_info):
        name = device_info['name']
        uuid = device_info['uuid']
        link = device_info['link']
        other_data = device_info['other_data']
        tag = device_info['tag']

        if uuid is None:
            device_type = RevealerDeviceType.OTHER
            state = "normal"
        elif device_info['uuid'] != "":
            device_type = RevealerDeviceType.OUR
            state = "normal"
        else:
            device_type = RevealerDeviceType.OUR
            state = "disabled"

        button.reinit(
            command_change=lambda:
            self.settings_func(name, uuid, link),
            command_view=lambda: self.properties_view_func(other_data, link),
            tag=tag, device_type=device_type, state=state
        )

    def ssdp_row_reinit(self, device_widget, link_widget, button_widget, device_info):

        tag = device_info['tag']
        link = device_info['link']
        uuid = device_info['uuid']
        other_data = device_info['other_data']

        device_font_weight = 'bold'
        if uuid is None:
            device_font_weight = ''

        # device label
        device_widget.configure(text=device_info['name'])
        device_widget.configure(font=(self.main_font.name, self.main_font.actual()['size'],
                                      device_font_weight))

        if tag != "not_local":

            # link label
            if link[0:4] == "http":
                link_widget.configure(text=link)
                link_widget.configure(font=(self.main_font.name, self.main_font.actual()['size'],
                                            'underline'))
                link_widget.configure(fg="blue")
                link_widget.configure(cursor=self.pointer_cursor)
            else:
                link_widget.configure(text=link)
                link_widget.configure(font=(self.main_font.name, self.main_font.actual()['size'],
                                            device_font_weight))
                link_widget.configure(fg=DEFAULT_TEXT_COLOR)
                link_widget.configure(cursor="arrow")

        else:
            link_widget.configure(text=link)
            link_widget.configure(font=(self.main_font.name, self.main_font.actual()['size'],
                                        device_font_weight))
            link_widget.configure(fg=DEFAULT_TEXT_COLOR)
            link_widget.configure(cursor="arrow")

        device_widget.tag = tag
        link_widget.tag = tag

        device_widget.link = link
        link_widget.link = link

        device_widget.uuid = uuid
        device_widget.other_data = other_data

        link_widget.uuid = uuid
        link_widget.other_data = other_data

        # update buttons
        self.button_reinit(button_widget, device_info)

    def add_ssdp_row(self, row, device_row: RevealerDeviceRow):

        device_info = device_row.get_dict()

        alpha_row = row

        # find correct color
        if alpha_row % 2 == 0:
            bg_color = self.EVEN_ROW_COLOR
        else:
            bg_color = DEFAULT_BG_COLOR

        middle_1 = Frame(self.main_table, takefocus=0, background=bg_color, width=2)
        middle_1.grid(row=alpha_row, column=1, sticky='news')
        middle_1.tag = device_info['tag']

        middle_3 = Frame(self.main_table, takefocus=0, background=bg_color, width=2)
        middle_3.grid(row=alpha_row, column=3, sticky='news')
        middle_3.tag = device_info['tag']

        font_weight = 'bold'

        if device_info['uuid'] is None:
            font_weight = ''

        if device_info['tag'] != "not_local":
            device = Label(self.main_table, text=device_info['name'], anchor="w", background=bg_color,
                           fg=DEFAULT_TEXT_COLOR,
                           font=(self.main_font.name, self.main_font.actual()['size'], font_weight))
            if device_info['link'][0:4] == "http":
                link_l = Label(self.main_table, text=device_info['link'], anchor="w", background=bg_color,
                               cursor=self.pointer_cursor,
                               fg="blue",
                               font=(self.main_font.name, self.main_font.actual()['size'], 'underline'))
            else:
                link_l = Label(self.main_table, text=device_info['link'], anchor="w", background=bg_color,
                               fg=DEFAULT_TEXT_COLOR,
                               font=(self.main_font.name, self.main_font.actual()['size'], font_weight))
        else:
            device = Label(self.main_table, text=device_info['name'], anchor="w", background=bg_color,
                           fg=DEFAULT_TEXT_COLOR,
                           font=(self.main_font.name, self.main_font.actual()['size'], font_weight))
            link_l = Label(self.main_table, text=device_info['link'], anchor="w", background=bg_color,
                           fg=DEFAULT_TEXT_COLOR,
                           font=(self.main_font.name, self.main_font.actual()['size'], font_weight))

        link_l.grid(row=alpha_row, column=2, sticky="ew")
        device.grid(row=alpha_row, column=0, sticky="ew")

        device.tag = device_info['tag']
        link_l.tag = device_info['tag']

        device.link = device_info['link']
        link_l.link = device_info['link']

        device.uuid = device_info['uuid']
        device.other_data = device_info['other_data']

        link_l.uuid = device_info['uuid']
        link_l.other_data = device_info['other_data']

        # add settings button
        if device_info['uuid'] is None:
            button_settings = ButtonSettings(self.main_table, col=4, row=alpha_row, os_main_root=self.os_main_root,
                                             command_change=lambda:
                                             self.settings_func(device_info['name'], device_info['uuid'],
                                                                link_l['text']),
                                             command_view=lambda: self.properties_view_func(device_info['other_data'],
                                                                                            link_l['text']),
                                             bg_color=bg_color, width=1, tag=device_info['tag'],
                                             type=RevealerDeviceType.OTHER)
        elif device_info['uuid'] != "":
            button_settings = ButtonSettings(self.main_table, col=4, row=alpha_row, os_main_root=self.os_main_root,
                                             command_change=lambda:
                                             self.settings_func(device_info['name'], device_info['uuid'],
                                                                link_l['text']),
                                             command_view=lambda: self.properties_view_func(device_info['other_data'],
                                                                                            link_l['text']),
                                             bg_color=bg_color, width=1, tag=device_info['tag'],
                                             type=RevealerDeviceType.OUR)
        else:
            button_settings = ButtonSettings(self.main_table, col=4, row=alpha_row, os_main_root=self.os_main_root,
                                             command_change=lambda:
                                             self.settings_func(device_info['name'], device_info['uuid'],
                                                                link_l['text']),
                                             command_view=lambda: self.properties_view_func(device_info['other_data'],
                                                                                            link_l['text']),
                                             bg_color=bg_color, width=1, tag=device_info['tag'],
                                             state="disabled", type=RevealerDeviceType.OUR)

        # bind double left click and right click
        # bind left-click to 'open_link'
        link_l.bind("<Button-1>", self.left_click_func)

        # bind right-click to 'change_ip'
        link_l.bind("<Button-3>", self.right_click_func)
        device.bind("<Button-3>", self.right_click_func)

        row_widgets = [device, link_l, button_settings]
        self.ssdp_rows.append(row_widgets)

        self.last_row += 1

    def add_legacy_headers(self, row):
        # add two blank lines
        blank = Label(self.main_table, text="", anchor="w", background=DEFAULT_BG_COLOR)
        blank.grid(row=row, column=0, sticky="ew")
        blank.tag = self.BLANK_LINE_TAG

        blank = Frame(self.main_table, takefocus=0, background=DEFAULT_BG_COLOR, width=2)
        blank.grid(row=row, column=1, sticky="news")
        blank.tag = self.BLANK_LINE_TAG

        blank = Label(self.main_table, text="", anchor="w", background=DEFAULT_BG_COLOR)
        blank.grid(row=row, column=2, sticky="ew")
        blank.tag = self.BLANK_LINE_TAG

        blank = Frame(self.main_table, takefocus=0, background=DEFAULT_BG_COLOR, width=2)
        blank.grid(row=row, column=3, sticky="news")
        blank.tag = self.BLANK_LINE_TAG

        blank = Frame(self.main_table, takefocus=0, background=DEFAULT_BG_COLOR, width=2)
        blank.grid(row=row, column=4, sticky="news")
        blank.tag = self.BLANK_LINE_TAG

        blank = Label(self.main_table, text="", anchor="w", background=DEFAULT_BG_COLOR)
        blank.grid(row=row + 1, column=0, sticky="ew")
        blank.tag = self.BLANK_LINE_TAG

        blank = Frame(self.main_table, takefocus=0, background=DEFAULT_BG_COLOR, width=2)
        blank.grid(row=row + 1, column=1, sticky="news")
        blank.tag = self.BLANK_LINE_TAG

        blank = Label(self.main_table, text="", anchor="w", background=DEFAULT_BG_COLOR)
        blank.grid(row=row + 1, column=2, sticky="ew")
        blank.tag = self.BLANK_LINE_TAG

        blank = Frame(self.main_table, takefocus=0, background=DEFAULT_BG_COLOR, width=2)
        blank.grid(row=row + 1, column=3, sticky="news")
        blank.tag = self.BLANK_LINE_TAG

        blank = Frame(self.main_table, takefocus=0, background=DEFAULT_BG_COLOR, width=2)
        blank.grid(row=row + 1, column=4, sticky="news")
        blank.tag = self.BLANK_LINE_TAG

        # add additional header line
        # add headers
        header_1 = Label(self.main_table, text="Legacy Protocol Devices", anchor="center", fg=DEFAULT_TEXT_COLOR,
                         background=self.HEADER_COLOR)
        header_1.grid(row=row + 2, column=0, sticky="ew")
        header_1.tag = self.ADDITIONAL_HEADER_TAG

        header_2 = ttk.Separator(self.main_table, takefocus=0, orient=VERTICAL)
        header_2.grid(row=row + 2, column=1, sticky="ns")
        header_2.tag = self.ADDITIONAL_HEADER_TAG

        header_3 = Label(self.main_table, text="URL", anchor="center", background=self.HEADER_COLOR, height=0,
                         fg=DEFAULT_TEXT_COLOR)
        header_3.grid(row=row + 2, column=2, sticky="ew")
        header_3.tag = self.ADDITIONAL_HEADER_TAG

        header_4 = ttk.Separator(self.main_table, takefocus=0, orient=VERTICAL)
        header_4.grid(row=row + 2, column=3, sticky="ns")
        header_4.tag = self.ADDITIONAL_HEADER_TAG

        blank = Frame(self.main_table, takefocus=0, background=self.HEADER_COLOR, width=2)
        blank.grid(row=row + 2, column=4, sticky="news")
        blank.tag = self.BLANK_LINE_TAG

    def add_legacy_row(self, row, device_row: RevealerDeviceRow):

        device_info = device_row.get_dict()

        alpha_row = row

        # find correct color
        if (alpha_row - self.LEGACY_HEADER_ROW + 1) % 2 == 0:
            bg_color = self.EVEN_ROW_COLOR
        else:
            bg_color = DEFAULT_BG_COLOR

        middle = Frame(self.main_table, takefocus=0, background=bg_color, width=2)
        middle.grid(row=alpha_row, column=1, sticky="news")
        middle.tag = device_info['tag']

        middle = Frame(self.main_table, takefocus=0, background=bg_color, width=2)
        middle.grid(row=alpha_row, column=3, sticky="news")
        middle.tag = device_info['tag']

        if device_info['tag'] != "not_local":
            device = Label(self.main_table, text=device_info['name'], anchor="w", background=bg_color,
                           fg=DEFAULT_TEXT_COLOR,
                           font=(self.main_font.name, self.main_font.actual()['size'], 'bold'))
            link = Label(self.main_table, text=device_info['link'], anchor="w", background=bg_color,
                         cursor=self.pointer_cursor,
                         fg="blue", font=(self.main_font.name, self.main_font.actual()['size'], 'underline'))
        else:
            device = Label(self.main_table, text=device_info['name'], anchor="w", background=bg_color)
            link = Label(self.main_table, text=device_info['link'], anchor="w", background=bg_color,
                         fg=DEFAULT_TEXT_COLOR,
                         font=(self.main_font.name, self.main_font.actual()['size'], ''))

        link.grid(row=alpha_row, column=2, sticky="ew")
        device.grid(row=alpha_row, column=0, sticky="ew")

        device.tag = device_info['tag']
        link.tag = device_info['tag']

        device.link = link['text']
        link.link = link['text']

        blank_settings = Frame(self.main_table, takefocus=0, background=bg_color, width=2)
        blank_settings.grid(row=alpha_row, column=4, sticky='news')
        blank_settings.tag = device_info['tag']

        # bind left-click to 'open_link'
        link.bind("<Button-1>", self.left_click_func)

        row_widgets = [device, link]

        self.legacy_rows.append(row_widgets)

    def delete_all_rows(self):
        self.last_row = 1
        self.legacy_last_row = 0

        self.ssdp_rows = []
        self.legacy_rows = []

        # self.device_list.clear_all()

        for i in self.main_table.winfo_children():
            if hasattr(i, 'tag'):
                # destroy all children which is not header
                if not i.tag == self.HEADER_TAG:
                    i.destroy()
            else:
                # and if does not have any tag at all
                i.destroy()

    def delete_to_widget(self, widget_n):
        widgets_arr = self.main_table.winfo_children()
        for i in range(len(widgets_arr)):
            if hasattr(widgets_arr[i], 'destroy_tag'):
                # destroy all children which is not header
                if widgets_arr[i].destroy_tag == '1':
                    widgets_arr[i].grid_forget()
                    widgets_arr[i].destroy()

    def add_row_ssdp_item(self, name, link, ip_address, uuid, other_data, tag):

        # we need to sort alphabetically at every moment
        # so... ignore the new row i guess
        # first of all check if had this object already

        # for this aim we parse uuid since we add uuid here only for our devices
        if uuid is None:
            # other device
            type = RevealerDeviceType.OTHER
        else:
            # our device
            type = RevealerDeviceType.OUR

        self.device_list.add_device(name=name, link=link, ip_address=ip_address, uuid=uuid, other_data=other_data,
                                    tag=tag, device_type=type, legacy=False)

        return

    def _set_row_color(self, row, additional_row, widget, subtract_legacy_header_row: bool):
        subtruhend = self.legacy_header_row if subtract_legacy_header_row else 0
        if (row + additional_row - subtruhend) % 2 == 0:
            widget["background"] = self.EVEN_ROW_COLOR
            if hasattr(widget, 'button'):
                widget.button.change_button_color(self.EVEN_ROW_COLOR)
        else:
            widget["background"] = DEFAULT_BG_COLOR
            if hasattr(widget, 'button'):
                widget.button.change_button_color(DEFAULT_BG_COLOR)

    def add_row_old_item(self, name, link, tag):

        self.device_list.add_device(
            name=name,
            device_type=None,
            link=link,
            ip_address=name,
            other_data=None,
            uuid=None,
            tag=tag,
            legacy=True
        )

        return


class ButtonSettings:
    ACTIVE_COLOR = "#e0e0e0"
    TOOLTIP_BG_COLOR = DEFAULT_BG_COLOR
    TOOLTIP_TIMEOUT = 0.75

    def __init__(self, master, col, row, command_change, command_view, os_main_root,
                 bg_color=DEFAULT_BG_COLOR, width=21,
                 tag=RevealerDeviceTag.LOCAL, state="normal", type=RevealerDeviceType.OUR):
        self.frame = Frame(master, background=bg_color, width=width, height=10)
        self.frame.grid(column=col, row=row, sticky='news')
        self.frame.propagate(False)
        self.frame.tag = tag

        self.frame.button = self
        self.bg_color = bg_color

        # os.path.dirname(__file__) to the main.py file
        # it is important to use this specific file path for correct mac os app bundle working
        self.os_main_root = os_main_root

        photo = PhotoImage(file=os.path.join(self.os_main_root, 'resources/settings2.png'))

        text_settings = "Change network settings..."

        # try to use mac os specific cursor - if exception is raised we are not on mac os and should use default
        self.pointer_cursor = CURSOR_POINTER_MACOS
        try:
            test_label = Label(master, text='', cursor=self.pointer_cursor)
            test_label.destroy()
        except TclError:
            self.pointer_cursor = CURSOR_POINTER

        if state == "normal":
            cursor = self.pointer_cursor
            # flag for indication if this button should be enabled for working after search is finished
            self.frame.button_flag = True
        else:
            cursor = "question_arrow"
            text_settings += "\n\nChange of the network settings in this firmware version is unavailable"
            # flag for indication if this button should not be enabled for working after search is finished
            self.frame.button_flag = False

        if type == RevealerDeviceType.OUR:
            button = Button(self.frame, image=photo, command=command_change, relief="flat", bg=bg_color, cursor=cursor,
                            highlightbackground=bg_color)
            button.grid(column=1, row=0, ipadx=0, ipady=0, padx=0, pady=0)
            button.image = photo
            button.bg_default = bg_color
            button["state"] = state

            button['activebackground'] = self.ACTIVE_COLOR

            self._change_hovertip = Hovertip(button, text=text_settings, hover_delay=1000)

            button.bind("<Leave>", self._on_leave, add="+")
            button.bind("<Enter>", self._on_enter, add="+")

            self._button_change = button
        else:
            self._change_hovertip = None
            self._button_change = None

        photo = PhotoImage(file=os.path.join(self.os_main_root, 'resources/properties.png'))

        button = Button(self.frame, image=photo, command=command_view, relief="flat", bg=bg_color,
                        cursor=self.pointer_cursor, highlightbackground=bg_color)
        button.grid(column=0, row=0, ipadx=0, ipady=0, padx=0, pady=0)
        button.image = photo
        button.bg_default = bg_color

        button['activebackground'] = self.ACTIVE_COLOR

        button.bind("<Leave>", self._on_leave)
        button.bind("<Enter>", self._on_enter)

        Hovertip(button, text="Device information", hover_delay=1000)

        button.bind("<Leave>", self._on_leave, add="+")
        button.bind("<Enter>", self._on_enter, add="+")

        self._button_view = button

    def reinit(self, command_view, command_change, tag, device_type, state="normal"):
        """
        Method of reinitialization of the buttons

        :param command_view:
        :param command_change:
        :param device_type:
        :param tag:
        :param state:
        :return:
        """
        # update frame tag
        self.frame.tag = tag

        # update button settings widget
        photo = PhotoImage(file=os.path.join(self.os_main_root, 'resources/settings2.png'))

        text_settings = "Change network settings..."

        if state == "normal":
            cursor = self.pointer_cursor
            # flag for indication if this button should be enabled for working after search is finished
            self.frame.button_flag = True
        else:
            cursor = "question_arrow"
            text_settings += "\n\nChange of the network settings in this firmware version is unavailable"
            # flag for indication if this button should not be enabled for working after search is finished
            self.frame.button_flag = False

        if device_type == RevealerDeviceType.OUR and self._button_change is None:
            # add button if it doesn't exist
            button = Button(self.frame, image=photo, command=command_change, relief="flat",
                            bg=self.bg_color, cursor=cursor,
                            highlightbackground=self.bg_color)
            button.grid(column=1, row=0, ipadx=0, ipady=0, padx=0, pady=0)
            button.image = photo
            button.bg_default = self.bg_color
            button["state"] = state

            button['activebackground'] = self.ACTIVE_COLOR

            self._change_hovertip = Hovertip(button, text=text_settings, hover_delay=1000)

            button.bind("<Leave>", self._on_leave, add="+")
            button.bind("<Enter>", self._on_enter, add="+")

            self._button_change = button
        elif device_type == RevealerDeviceType.OUR and self._button_change is not None:
            self._button_change.configure(command=command_change)
            self._button_change.configure(cursor=cursor)
            self._change_hovertip.text = text_settings
        elif device_type != RevealerDeviceType.OUR and self._button_change is not None:
            self._button_change.destroy()
            self._button_change = None

        # update properties button
        self._button_view.configure(command=command_view)

    def disable(self):
        """
        Disable button.
        :return:
        """
        if self._button_change is not None:
            self._button_change["state"] = "disabled"
            self._button_change.update()

    def enable(self):
        if self._button_change is not None:
            self._button_change["state"] = "normal"
            self._button_change.update()

    def change_button_color(self, color):
        if self._button_change is not None:
            self._button_change.configure(bg=color, highlightbackground=color)
            self._button_change.bg_default = color

        self._button_view.configure(bg=color, highlightbackground=color)
        self._button_view.bg_default = color

    def _on_enter(self, event):
        if event.widget["state"] != "disabled":
            event.widget.configure(bg=event.widget['activebackground'],
                                   highlightbackground=event.widget['activebackground'])

    def _on_leave(self, event):
        if event.widget["state"] != "disabled":
            event.widget.configure(bg=event.widget.bg_default, highlightbackground=event.widget.bg_default)
