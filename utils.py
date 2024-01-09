import base64
import os
import re
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
ExportDir = os.path.join(os.path.expanduser("~"), "renderup_res")
MESSAGE_TAG = "RenderUP"

# 图标
iconlib = {
    "setting": QIcon(PluginDir + "/icons/setting.svg"),
    "image": QIcon(PluginDir + "/icons/image.svg"),
    "render": QIcon(PluginDir + "/icons/render.svg"),
    "logo": QIcon(PluginDir + "/icons/mainlogo.svg"),
    'export': QIcon(PluginDir + "/icons/mainlogo.svg"),
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

metro_line_color_dict = {
    '1': '#00B140',
    '2': '#B94700',
    '3': '#00A9E0',
    '4': '#DA291C',
    '5': '#A05EB5',
    '6': '#00C7B1',
    '7': '#0033A0',
    '8': '#E45DBF',
    '9': '#7B6469',
    '10': '#F8779E',
    '11': '#672146',
    '12': '#A192B2',
    '13': '#DE7C00',
    '14': '#F2C75C',
    '15': '#84BD00',
    '16': '#1E22AA',
    '17': '#017D83',
    '18': '#1E90FF',
    '19': '#439F6C',
    '20': '#88DBDF',
    '21': '#8F6740',
    '22': '#1B9062',
    '23': '#A9624A',
    '24': '#F44F19',
    '25': '#4A6AE0',
    '26': '#C82C8A',
    '27': '#3E8065',
    '28': '#8777E7',
    '29': '#A23049',
    '30': '#CB9B47',
    '31': '#CD7FF2',
    '32': '#980CA0',
    '34': '#168773'
}

poi_type_color_dict = {
    '学校': '#42C5AD',
    '医院': '#F47494',
    '大型公服': '#ED7D31',
    '商业服务': '#C00000'
}

class default_field:
    name_metro_line_id = 'lineID'
    name_metro_station_name = 'name'
    name_poi_type = 'type'
    name_poi = 'name'
    name_block = 'landid'


EXTRAMAPS_PATH = os.path.join(PluginDir, "extramaps.yml")
with open(EXTRAMAPS_PATH, encoding="utf-8") as f:
    extra_maps = yaml.load(f, Loader=yaml.FullLoader)


class single_window:
    m_frmRender = None  # 器窗口只能打开一个
    m_frmSetting = None

@dataclass
class PluginConfig:
    key: str
    keyisvalid: bool
    random_enabled: bool = True
    subdomain: str = "0"
    extramap_enabled: bool = True
    lastpath: str = os.path.expanduser("~")
    out_path: str = ""
    out_width: int = 1920
    out_height: int = 1080
    out_resolution: int = 300
    out_format: str = "png"
    draw_circle: bool = False
    radius: float = 0.0


def epsg_code(crs: QgsCoordinateReferenceSystem):
    if not crs.isValid():
        return -1
    else:
        return int(crs.authid()[5:])


def get_qset_name(key: str) -> str:
    section_tianditu = ["key", "random", "keyisvalid", "subdomain"]
    section_layers = ["extramap",  "block_layer_id"]
    section_settings = ["lastpath", "out_path", "out_width", "out_height", "out_resolution", "out_format", "draw_circle", "radius"]
    if key in section_tianditu:
        return f"{PLUGIN_NAME}/tianditu/{key}"
    if key in section_layers:
        return f"{PLUGIN_NAME}/layers/{key}"
    if key in section_settings:
        return f"{PLUGIN_NAME}/settings/{key}"
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


def check_crs(crs: QgsCoordinateReferenceSystem):
    # crs = iface.mapCanvas().mapSettings().destinationCrs()
    if not crs.isValid():
        return False

    if crs == QgsCoordinateReferenceSystem("EPSG:3857") or crs == QgsCoordinateReferenceSystem("EPSG:4547") or \
        crs == QgsCoordinateReferenceSystem("EPSG:4490") or crs == QgsCoordinateReferenceSystem("EPSG:4326"):

        # QgsMessageLog.logMessage("插件{}: 当前坐标系统{}, 符合输入要求.".format(PLUGIN_NAME, crs.authid()), tag="Plugins", level=Qgis.MessageLevel.Info)

        return True
    else:
        # QgsMessageLog.logMessage("插件{}: 当前坐标系统{}, 不符合输入要求.".format(PLUGIN_NAME, crs.authid()), tag="Plugins", level=Qgis.MessageLevel.Warning)
        return False


#  不考虑字段名的大小写敏感
def get_field_index_no_case(layer, match_name):
    field_names = layer.dataProvider().fields().names()

    index = 0
    for field_name in field_names:
        ret = re.search(field_name, match_name, re.IGNORECASE)
        if ret is not None:
            return index, field_name
        index += 1
    return -1, match_name


def embedSymbol(symbol):
    try:
        layer_type = symbol.layerType()
        if layer_type == 'SvgMarker':
            svg_path = symbol.path()
            if svg_path[:7] == 'base64:':
                print('svg symbol already embedded')
            else:
                encoded_string = ""
                with open(svg_path, "rb") as svg:
                    encoded_string = base64.b64encode(svg.read())
                    decoded_string = encoded_string.decode("utf-8")
                    svg_content = 'base64:' + decoded_string
                    symbol.setPath(svg_content)
                    print('embedded svg symbol')
        else:
            print('not an svg symbol')
    except Exception as err:
        print(err)