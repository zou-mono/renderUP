import os
from dataclasses import dataclass
from multiprocessing.pool import ThreadPool

import requests
import yaml
from PyQt5.QtGui import QIcon
from qgis._core import Qgis, QgsCoordinateReferenceSystem, QgsMessageLog

PLUGIN_NAME = "renderUP"
current_qgis_version = Qgis.QGIS_VERSION_INT

TIANDITU_HOME_URL = "https://www.tianditu.gov.cn/"
HEADER = {
    "User-Agent": "Mozilla/5.0 QGIS/32400/Windows 10 Version 2009",
    "Referer": "https://www.tianditu.gov.cn/",
}

PluginDir = os.path.dirname(__file__)

# 图标
iconlib = {
    "setting": QIcon(PluginDir + "/icons/setting.svg"),
    "image": QIcon(PluginDir + "/icons/image.svg"),
    "render": QIcon(PluginDir + "/icons/render.svg"),
    "logo": QIcon(PluginDir + "/icons/mainlogo.svg"),
    "tianditu": QIcon(PluginDir + "/icons/map_tianditu.svg"),
    "extra_map": QIcon(PluginDir + "/icons/extra_map.svg")
}

TianMapInfo = {
    "vec": "天地图-矢量底图",
    "cva": "天地图-矢量注记",
    "img": "天地图-影像底图",
    "cia": "天地图-影像注记",
    "ter": "天地图-地形晕染",
    "cta": "天地图-地形注记",
    "eva": "天地图-英文矢量注记",
    "eia": "天地图-英文影像注记"
}

EXTRAMAPS_PATH = os.path.join(PluginDir, "extramaps.yml")
with open(EXTRAMAPS_PATH, encoding="utf-8") as f:
    extra_maps = yaml.load(f, Loader=yaml.FullLoader)


@dataclass
class PluginConfig:
    key: str
    keyisvalid: bool
    random_enabled: bool
    subdomain: str
    extramap_enabled: bool
    lastpath: str


def get_qset_name(key: str) -> str:
    section_tianditu = ["key", "random", "keyisvalid", "subdomain"]
    section_other = ["extramap", "lastpath"]
    if key in section_tianditu:
        return f"{PLUGIN_NAME}/tianditu/{key}"
    if key in section_other:
        return f"{PLUGIN_NAME}/extra/{key}"
    return ""


def tianditu_map_url(maptype: str, token: str, subdomain: str) -> str:
    """
    返回天地图url

    Args:
        maptype (str): 类型
        token (str): 天地图key
        subdomain (str): 使用的子域名

    Returns:
        str: 返回天地图XYZ瓦片地址
    """
    url = f"https://{subdomain}.tianditu.gov.cn/"
    url += (
        f"{maptype}_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER={maptype}"
    )
    url += "&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TileCol={x}&TileRow={y}&TileMatrix={z}"
    url += f"&tk={token}"
    return url


def check_url_status(url: str) -> object:
    """
    检查url状态
    Args:
        url (str): url

    Returns:
        object: {"code": 0}
        code:
            0: 正常
            1: 非法key
            12: 权限类型错误
            1000: 未知错误
    """
    res = requests.get(url, headers=HEADER, timeout=10)
    msg = {"code": 0}
    if res.status_code == 403:
        msg["code"] = res.json()["code"]  # 1:非法key 12:权限类型错误
        msg["msg"] = res.json()["msg"]
        msg["resolve"] = res.json()["resolve"]
    elif res.status_code == 200:
        msg["code"] = 0
    else:
        msg["code"] = 1000  # 未知错误
        msg["msg"] = "未知错误 "
        msg["resolve"] = f"错误代码:{res.status_code}"
    return msg


def check_subdomain(url: str) -> int:
    """对子域名进行测速

    Args:
        url (str): 瓦片url

    Returns:
        int: 子域名对应的延迟数(毫秒), -1 表示连接失败
    """
    response = requests.get(url, headers=HEADER, timeout=8)
    if response.status_code == 200:
        millisecond = response.elapsed.total_seconds() * 1000
    else:
        millisecond = -1
    return int(millisecond)


def check_subdomains(url_list: list) -> list:
    """对子域名列表进行测速

    Args:
        url_list (list): 由不同子域名组成的瓦片url列表

    Returns:
        list: 每个子域名对应的延迟数(毫秒)组成的列表
    """
    pool = ThreadPool(4)
    ping_list = pool.map(check_subdomain, url_list)
    pool.close()
    pool.join()
    return ["❌" if x == -1 else f"{x} ms" for x in ping_list]


def check_key_format(key: str) -> object:
    """检查key格式

    Args:
        key (str): 天地图key

    Returns:
        object:
            "key_length_error": key的长度有误,
            "has_special_character": 含有除字母数字外的其他字符
    """
    correct_length = 32
    key_length = len(key)
    key_length_error = False
    if key_length != correct_length:
        key_length_error = True
    return {
        "key_length_error": key_length_error,
        "has_special_character": not key.isalnum(),
    }


def find_nearest_number_index(numbers_list, target):
    min_difference = float("inf")
    nearest_index = None

    for i, number in enumerate(numbers_list):
        difference = abs(number - target)
        if difference < min_difference:
            min_difference = difference
            nearest_index = i

    return nearest_index


def check_crs(iface):
    crs = iface.mapCanvas().mapSettings().destinationCrs()

    if crs == QgsCoordinateReferenceSystem("EPSG:3857") or crs == QgsCoordinateReferenceSystem("EPSG:4547") or \
        crs == QgsCoordinateReferenceSystem("EPSG:4490") or crs == QgsCoordinateReferenceSystem("EPSG:4326"):

        QgsMessageLog.logMessage("插件{}: 当前坐标系统{}, 符合输入要求.".format(PLUGIN_NAME, crs.authid()), tag="Plugins", level=Qgis.MessageLevel.Info)

        return True
    else:
        QgsMessageLog.logMessage("插件{}: 当前坐标系统{}, 不符合输入要求.".format(PLUGIN_NAME, crs.authid()), tag="Plugins", level=Qgis.MessageLevel.Warning)
        return False
