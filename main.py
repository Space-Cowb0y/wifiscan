import io
import os
import pkgutil
import subprocess
import sys
import tempfile
import datetime
from typing import Callable, List, Optional
import pandas as pd
import sqlite3
import time
from fpdf import FPDF
from ctypes import *
from ctypes.wintypes import *
from comtypes import GUID
#from datetime import date
from functools import reduce
#import importlib.util

""" # Definir o caminho para o arquivo cyberAPI.py
module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), r'C:\\Users\\e5693423\\OneDrive - FIS\\Documents\\proj', 'geral', 'cyberAPI.py'))

# Carregar o módulo dinamicamente
spec = importlib.util.spec_from_file_location("cyberAPI", module_path)
cyberAPI = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cyberAPI)

# Exemplo de uso das funções do cyberAPI
cyberAPI.login() """


class WLAN_RAW_DATA(Structure):
    _fields_ = [
        ("dwDataSize", DWORD),
        ("DataBlob", c_byte * 1)
    ]


class DOT11_SSID(Structure):
    _fields_ = [("uSSIDLength", c_ulong),
                ("ucSSID", c_char * 32)]


class WLAN_INTERFACE_INFO(Structure):
    _fields_ = [
        ("InterfaceGuid", GUID),
        ("strInterfaceDescription", c_wchar * 256),
        ("isState", c_uint)
    ]


class WLAN_INTERFACE_INFO_LIST(Structure):
    _fields_ = [
        ("dwNumberOfItems", DWORD),
        ("dwIndex", DWORD),
        ("InterfaceInfo", WLAN_INTERFACE_INFO * 1)
    ]


class WindllWlanApi:
    SUCCESS = 0

    def __init__(self):
        self.native_wifi = windll.wlanapi
        self._handle = HANDLE()
        self._nego_version = DWORD()
        self._ifaces = pointer(WLAN_INTERFACE_INFO_LIST())

    def wlan_func_generator(self, func, argtypes, restypes):
        func.argtypes = argtypes
        func.restypes = restypes
        return func

    def wlan_open_handle(self, client_version=2):
        f = self.wlan_func_generator(self.native_wifi.WlanOpenHandle,
                                     [DWORD, c_void_p, POINTER(DWORD), POINTER(HANDLE)],
                                     [DWORD])

        return f(client_version, None, byref(self._nego_version), byref(self._handle))

    def wlan_enum_interfaces(self):
        f = self.wlan_func_generator(self.native_wifi.WlanEnumInterfaces,
                                     [HANDLE, c_void_p, POINTER(POINTER(WLAN_INTERFACE_INFO_LIST))],
                                     [DWORD])

        return f(self._handle, None, byref(self._ifaces))

    def wlan_scan(self, iface_guid):
        f = self.wlan_func_generator(self.native_wifi.WlanScan,
                                 [HANDLE, POINTER(GUID), POINTER(DOT11_SSID), POINTER(WLAN_RAW_DATA), c_void_p],
                                 [DWORD])

        return f(self._handle, iface_guid, None, None, None)

    def get_interfaes(self):
        interfaces = []
        _interfaces = cast(self._ifaces.contents.InterfaceInfo,
                           POINTER(WLAN_INTERFACE_INFO))
        for i in range(0, self._ifaces.contents.dwNumberOfItems):
            iface = {}
            iface['guid'] = _interfaces[i].InterfaceGuid
            iface['name'] = _interfaces[i].strInterfaceDescription
            interfaces.append(iface)

        return interfaces


class WinWiFi:
    @classmethod
    def get_profile_template(cls) -> str:
        return pkgutil.get_data(__package__, 'data/profile-template.xml').decode()

    @classmethod
    def netsh(cls, args: List[str], timeout: int = 3, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
                ['netsh'] + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=timeout, check=check, encoding=sys.stdout.encoding)

    @classmethod
    def get_profiles(cls, callback: Callable = lambda x: None) -> List[str]:
        profiles: List[str] = []

        raw_data: str = cls.netsh(['wlan', 'show', 'profiles'], check=False).stdout

        line: str
        for line in raw_data.splitlines():
            if ' : ' not in line:
                continue
            profiles.append(line.split(' : ', maxsplit=1)[1].strip())

        callback(raw_data)

        return profiles

    @classmethod
    def gen_profile(cls, ssid: str = '', auth: str = '', encrypt: str = '', passwd: str = '', remember: bool = True) \
            -> str:
        profile: str = cls.get_profile_template()

        profile = profile.replace('{ssid}', ssid)
        profile = profile.replace('{connmode}', 'auto' if remember else 'manual')

        if not passwd:
            profile = profile[:profile.index('<sharedKey>')] + \
                profile[profile.index('</sharedKey>')+len('</sharedKey>'):]
            profile = profile.replace('{auth}', 'open')
            profile = profile.replace('{encrypt}', 'none')

        return profile

    @classmethod
    def add_profile(cls, profile: str):
        fd: io.RawIOBase
        path: str
        fd, path = tempfile.mkstemp()

        os.write(fd, profile.encode())
        cls.netsh(['wlan', 'add', 'profile', 'filename={}'.format(path)])

        os.close(fd)
        os.remove(path)

    @classmethod
    def scan(cls, callback: Callable = lambda x: None) -> List['WiFiAp']:
        authf = []
        win_dll_wlan = WindllWlanApi()
        now = datetime.datetime.now()
        area = input('Qual área esse scan se refere? ')
        if win_dll_wlan.wlan_open_handle() is not win_dll_wlan.SUCCESS:
            raise RuntimeError('Wlan dll open handle failed !')

        if win_dll_wlan.wlan_enum_interfaces() is not win_dll_wlan.SUCCESS:
            raise RuntimeError('Wlan dll enum interfaces failed !')

        wlan_interfaces = win_dll_wlan.get_interfaes()
        if len(wlan_interfaces) == 0:
            raise RuntimeError('Do not get any wlan interfaces !')

        win_dll_wlan.wlan_scan(byref(wlan_interfaces[0]['guid']))
        time.sleep(5)

        cp: subprocess.CompletedProcess = cls.netsh(['wlan', 'show', 'networks', 'mode=bssid'])
        callback(cp.stdout)
        outp = list(map(WiFiAp.parse_netsh, [out for out in cp.stdout.split('\n\n') if out.startswith('SSID')]))
        
        networks = []
        lines = cp.stdout.splitlines()
        current_network = {}
        for line in lines:
            if line.startswith("SSID"):
                if current_network:
                    networks.append(current_network)
                current_network = {"ssid": line.split(":", 1)[1].strip(), "auth": "", "encrypt": "", "bssid": "", "strength": 0, "Banda":""}
            elif "Autenticação" in line or "Authentication" in line:
                current_network["auth"] = line.split(":", 1)[1].strip()
            elif "Criptografia" in line or "Encryption" in line:
                current_network["encrypt"] = line.split(":", 1)[1].strip()
            elif "BSSID" in line:
                current_network["bssid"] = line.split(":", 1)[1].strip()
            elif "Sinal" in line or "Signal" in line:
                current_network["strength"] = int(line.split(":", 1)[1].strip().replace('%', ''))
            elif "Banda" in line or "Band" in line:
                current_network["Banda"] = line.split(":", 1)[1].strip()
        if current_network:
            networks.append(current_network)


        # Verificar se os dados foram extraídos corretamente
        for network in networks:
            print(network)

        # Salvar no banco de dados SQLite
        conn = sqlite3.connect('wifi_scans.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS scans
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      area TEXT, ssid TEXT, auth TEXT, encrypt TEXT, bssid TEXT, strength INTEGER, banda TEXT, datetime TEXT)''')
        for network in networks:
            c.execute("INSERT INTO scans (area, ssid, auth, encrypt, bssid, strength, banda, datetime) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (area, network["ssid"], network["auth"], network["encrypt"], network["bssid"], network["strength"], network["Banda"],now.strftime("%d/%m/%Y %H:%M:%S")))
        conn.commit()
        conn.close()
        
        conn = sqlite3.connect('wifi_scans.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS open_scans
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      area TEXT, ssid TEXT, auth TEXT, encrypt TEXT, strength INTEGER, banda TEXT, datetime TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS open_bssids
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      scan_id INTEGER,
                      bssid TEXT,
                      FOREIGN KEY(scan_id) REFERENCES open_scans(id))''')
        for network in networks:
            if network["auth"].lower() == "open" or network["auth"].lower() == "aberta":
                c.execute("INSERT INTO open_scans (area, ssid, auth, encrypt, strength, banda, datetime) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (area, network["ssid"], network["auth"], network["encrypt"], network["strength"], network["Banda"], now.strftime("%d/%m/%Y %H:%M:%S")))
                scan_id = c.lastrowid
                for bssid in network["bssids"]:
                    c.execute("INSERT INTO open_bssids (scan_id, bssid) VALUES (?, ?)", (scan_id, bssid))
        conn.commit()
        conn.close()



        """ 
        #save to csv
        with open('redes'+'.csv', "a") as f_x0:
            #open('%s.csv' % name, 'wb')
            f_x0.write('\n==================================\n')
            f_x0.write('                '+area+'          \n')
            f_x0.write('==================================\n')
            f_x0.write(now.strftime("%d/%m/%Y %H:%M:%S"))
            f_x0.write(cp.stdout)
        with open('RedesAbertas.csv', "a") as f_x0:
            f_x0.write('\n==================================\n')
            f_x0.write('                '+area+'          \n')
            f_x0.write('==================================\n')
            #for line in cp.stdout.splitlines():
            for i, line in enumerate(lines):
                if "SSID" in line:
                    ssidf = line.split(":", 1)[1].strip()
                elif"Authentication" in line and "Open" in line:
                    authf.append(ssidf)
                    bssidf = lines[i+2].split(":", 1)[1].strip()
                    authf.append(bssidf)
            if authf.__len__() > 0:
                f_x0.write('Numero de redes abertas: '+ (repr(int(authf.__len__()/2))) +';\n')
                f_x0.write('Nome das Redes Abertas:;BSSID das redes abertas; \n')
                for i, line in enumerate(authf):
                    if i< len(authf) -1:
                        f_x0.write('%s;%s;\n' % (authf[i],authf[i+1]))
            else:
                f_x0.write("Nenhuma rede aberta no range de " + area + ';\n')
            f_x0.write("data e hora da varredura: " + now.strftime("%d/%m/%Y %H:%M:%S"))      
        with open('redes.csv', "r") as f_x0:
            filedata = f_x0.read()
        filedata = filedata.replace('There are ','Foram encontradas ')
        filedata = filedata.replace("networks currently visible","Redes abertas")
        with open(area+'.csv', "w") as f_x0:
            f_x0.write(filedata)
 """
 
        # Salvar em PDF
        pdf_filename = area + '.pdf'
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Relatório de Redes Wi-Fi - Área: " + area, ln=True, align='C')
        pdf.cell(200, 10, txt="Data e Hora: " + now.strftime("%d/%m/%Y %H:%M:%S"), ln=True, align='C')
        for network in networks:
            pdf.cell(200, 10, txt="SSID: " + network["ssid"], ln=True)
            pdf.cell(200, 10, txt="Autenticação: " + network["auth"], ln=True)
            pdf.cell(200, 10, txt="Encriptação: " + network["encrypt"], ln=True)
            pdf.cell(200, 10, txt="Força do Sinal: " + str(network["strength"]) + "%", ln=True)
            pdf.cell(200, 10, txt="bssid: " + network["bssid"], ln=True)
            pdf.cell(200, 10, txt="", ln=True)  # Linha em branco para separar redes
        pdf.output(pdf_filename)


        

    @classmethod
    def get_interfaces(cls) -> List['WiFiInterface']:
        cp: subprocess.CompletedProcess = cls.netsh(['wlan', 'show', 'interfaces'])
        return list(map(WiFiInterface.parse_netsh,
                        [out for out in cp.stdout.split('\n\n') if out.startswith('    Name')]))

    @classmethod
    def get_connected_interfaces(cls) -> List['WiFiInterface']:
        return list(filter(lambda i: i.state == WiFiConstant.STATE_CONNECTED, cls.get_interfaces()))

    @classmethod
    def disable_interface(cls, interface: str):
        cls.netsh(['interface', 'set', 'interface', 'name={}'.format(interface), 'admin=disabled'], timeout=15)

    @classmethod
    def enable_interface(cls, interface: str):
        cls.netsh(['interface', 'set', 'interface', 'name={}'.format(interface), 'admin=enabled'], timeout=15)

    @classmethod
    def connect(cls, ssid: str, passwd: str = '', remember: bool = True):
        if not passwd:
            for i in range(3):
                aps: List['WiFiAp'] = cls.scan()
                ap: 'WiFiAp'
                if ssid in [ap.ssid for ap in aps]:
                    break
                time.sleep(5)
            else:
                raise RuntimeError('Cannot find Wi-Fi AP')

            if ssid not in cls.get_profiles():
                ap = [ap for ap in aps if ap.ssid == ssid][0]
                cls.add_profile(cls.gen_profile(
                    ssid=ssid, auth=ap.auth, encrypt=ap.encrypt, passwd=passwd, remember=remember))
            cls.netsh(['wlan', 'connect', 'name={}'.format(ssid)])

            for i in range(30):
                if list(filter(lambda it: it.ssid == ssid, WinWiFi.get_connected_interfaces())):
                    break
                time.sleep(1)
            else:
                raise RuntimeError('Cannot connect to Wi-Fi AP')

    @classmethod
    def disconnect(cls):
        cls.netsh(['wlan', 'disconnect'])

    @classmethod
    def forget(cls, *ssids: str):
        for ssid in ssids:
            cls.netsh(['wlan', 'delete', 'profile', ssid])           
    
   
class WiFiAp:
    @classmethod
    def parse_netsh(cls, raw_data: str) -> 'WiFiAp':
        ssid: str = ''
        auth: str = ''
        encrypt: str = ''
        bssid: str = ''
        strength: int = 0
        band: str = ''

        line: str
        for line in raw_data.splitlines():
            if ' : ' not in line:
                continue
            value: str = line.split(' : ', maxsplit=1)[1].strip()
            if line.startswith('SSID'):
                ssid = value
            elif line.startswith('    Authentication'):
                auth = value
            elif line.startswith('    Encryption'):
                encrypt = value
            elif line.startswith('    BSSID'):
                bssid = value.lower()
            elif line.startswith('         Signal'):
                strength = int(value[:-1])
            elif line.startswith('         Band'):
                band = value
        return cls(ssid=ssid, auth=auth, encrypt=encrypt, bssid=bssid, strength=strength, band=band, raw_data=raw_data)

    def __init__(
            self,
            ssid: str = '',
            auth: str = '',
            encrypt: str = '',
            bssid: str = '',
            strength: int = 0,
            band: str = '',
            raw_data: str = '',
    ):
        self._ssid: str = ssid
        self._auth: str = auth
        self._encrypt: str = encrypt
        self._bssid: str = bssid
        self._strength: int = strength
        self._band: str = band
        self._raw_data: str = raw_data

    @property
    def ssid(self) -> str:
        return self._ssid

    @property
    def auth(self) -> str:
        return self._auth

    @property
    def encrypt(self) -> str:
        return self._encrypt

    @property
    def bssid(self) -> str:
        return self._bssid

    @property
    def strength(self) -> int:
        return self._strength
    
    @property
    def band(self) -> str:
        return self._band

    @property
    def raw_data(self) -> str:
        return self._raw_data


class WiFiConstant:
    STATE_CONNECTED = 'connected'
    STATE_DISCONNECTED = 'disconnected'


class WiFiInterface:
    @classmethod
    def parse_netsh(cls, raw_data: str) -> 'WiFiInterface':
        name: str = ''
        state: str = ''
        ssid: str = ''
        bssid: str = ''

        line: str
        for line in raw_data.splitlines():
            if ' : ' not in line:
                continue
            value: str = line.split(' : ', maxsplit=1)[1].strip()
            if line.startswith('    Name'):
                name = value
            elif line.startswith('    State'):
                state = value
            elif line.startswith('    SSID'):
                ssid = value
            elif line.startswith('    BSSID'):
                bssid = value

        c: 'WiFiInterface' = cls(name=name, state=state)
        if ssid:
            c.ssid = ssid
        if bssid:
            c.bssid = bssid
        return c

    def __init__(
            self,
            name: str = '',
            state: str = '',
            ssid: Optional[str] = None,
            bssid: Optional[str] = None,
    ):
        self._name: str = name
        self._state: str = state
        self._ssid: Optional[str] = ssid
        self._bssid: Optional[str] = bssid

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> str:
        return self._state

    @property
    def ssid(self) -> Optional[str]:
        return self._ssid

    @ssid.setter
    def ssid(self, value: str):
        self._ssid = value

    @property
    def bssid(self) -> Optional[str]:
        return self._bssid

    @bssid.setter
    def bssid(self, value: str):
        self._bssid = value