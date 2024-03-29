import logging as log


class RevealerDeviceType:
    OUR = 0
    OTHER = 1


class RevealerDeviceTag:
    LOCAL = "local"
    LOCAL_OTHER = "local_other"
    NOT_LOCAL = "not_local"
    OLD_LOCAL = "old_local"


class RevealerDeviceRow:
    """
    Class of Device row information.
    """

    def __init__(self, device_name, device_type, device_info, device_link, device_ip_address, device_uuid, device_tag,
                 device_legacy=False, device_mipas=False):
        self.name = device_name
        self.type = device_type
        self.other_data = device_info
        self.link = device_link
        self.ip_address = device_ip_address
        self.uuid = device_uuid
        self.tag = device_tag
        self.legacy = device_legacy
        # flag to indicate that this is our device which support setting network settings via SSDP
        self.mipas = device_mipas

        self.row = 0

    def set_row(self, row):
        self.row = row

    def get_row(self):
        return self.row

    def reinit(self, device_name, device_type, device_info, device_link, device_ip_address, device_uuid, device_tag,
               device_legacy=False, device_mipas=False):
        self.name = device_name
        self.type = device_type
        self.other_data = device_info
        self.link = device_link
        self.ip_address = device_ip_address
        self.uuid = device_uuid
        self.tag = device_tag
        self.legacy = device_legacy
        # flag to indicate that this is our device which support setting network settings via SSDP
        self.mipas = device_mipas

        self.row = 0

    def deepcopy(self):
        return RevealerDeviceRow(
            device_name=self.name,
            device_type=self.type,
            device_info=self.other_data,
            device_link=self.link,
            device_ip_address=self.ip_address,
            device_uuid=self.uuid,
            device_tag=self.tag,
            device_legacy=self.legacy,
            device_mipas=self.mipas
        )

    def get_dict(self):
        row_dict = {
            'name': self.name,
            'type': self.type,
            'other_data': self.other_data,
            'link': self.link,
            'ip_address': self.ip_address,
            'uuid': self.uuid,
            'tag': self.tag,
            'legacy': self.legacy,
            'mipas': self.mipas
        }
        return row_dict


class RevealerDeviceList:
    """
    Class for storaging Revealer Device list with remembering rows and so on.

    """

    def __init__(self):

        self.ssdp_devices = []
        self.old_devices = []

        self.ssdp_dict = {}
        self.legacy_dict = {}
        self.ip_dict_whole = {}

    def clear_all(self):
        self.ssdp_devices = []
        self.old_devices = []

        self.ssdp_dict = {}
        self.legacy_dict = {}
        self.ip_dict_whole = {}

    def add_device(self, name, device_type, link, ip_address, other_data, uuid, tag, legacy, mipas_support=False):

        device_row = RevealerDeviceRow(
            device_name=name,
            device_type=device_type,
            device_info=other_data,
            device_link=link,
            device_ip_address=ip_address,
            device_uuid=uuid,
            device_tag=tag,
            device_legacy=legacy,
            device_mipas=mipas_support
        )

        if not legacy:
            row = self.add_device_to_ssdp_dict(device_row)
            if row is not None:
                device_row.set_row(row=row)
                log.debug(f"Add ssdp device {device_row.name} to row {row}")
                self.ssdp_devices.insert(row - 1, device_row)

        else:
            row = self.add_device_to_legacy_dict(device_row)
            if row is not None:
                device_row.set_row(row=row)
                self.old_devices.insert(row - 1, device_row)

    def print_old_devices(self):
        index = 0
        for device in self.old_devices:
            print(index, device.name)
            index += 1
        print()

    def add_device_to_ssdp_dict(self, device_row: RevealerDeviceRow):
        """
        Method which sort dictionary with ssdp found device for putting our devices higher in the list and sort in
        alphabetical order in our and other?

        :return: None
        """

        our_dict = {}
        other_dict = {}

        device_info = device_row.get_dict()

        device = device_info['name'] + device_info['link']
        device_type = device_info['type']

        uuid = device_info['uuid']
        if uuid is None:
            try:
                uuid = device_info['other_data']['UDN'][5:]
            except Exception:
                uuid = ''

        # check presence in the dict
        try:
            presence_whole = self.ip_dict_whole[device_info['ip_address']+uuid]
            log.debug(presence_whole)
            return None
        except KeyError:
            self.ip_dict_whole[device_info['ip_address']+uuid] = device_info['name']

        try:
            presence = self.ssdp_dict[device_info['name'] + device_info['link']]
            log.debug(presence)
            return None
        except KeyError:
            # find end of the our list to sort only them
            for ex_device in self.ssdp_dict:
                if self.ssdp_dict[ex_device]['type'] == RevealerDeviceType.OUR:
                    our_dict[ex_device] = self.ssdp_dict[ex_device]
                else:
                    other_dict[ex_device] = self.ssdp_dict[ex_device]

            if device_type == RevealerDeviceType.OUR:
                our_dict[device] = {'type': device_type}
                sorted_list = sorted(our_dict, key=lambda v: v.upper())
                alpha_row = sorted_list.index(device) + 1

            else:
                other_dict[device] = {'type': device_type}
                sorted_list = sorted(other_dict, key=lambda v: v.upper())
                alpha_row = sorted_list.index(device) + 1 + len(our_dict)

            self.ssdp_dict[device] = {'type': device_type}

            return alpha_row

    def add_device_to_legacy_dict(self, device_row):
        """
        Method which sort dictionary with found legacy device.

        :return: None
        """

        device_info = device_row.get_dict()

        name = device_info['name']
        link = device_info['link']

        try:
            presence_whole = self.ip_dict_whole[link]
            log.debug(presence_whole)
            return None
        except KeyError:
            self.ip_dict_whole[link] = name

            self.legacy_dict[name] = len(self.old_devices) + len(self.ssdp_devices) + 4

            sorted_list = sorted(self.legacy_dict)

            alpha_row = sorted_list.index(name) + 1  # + len(self.ssdp_devices) + 3

            return alpha_row
