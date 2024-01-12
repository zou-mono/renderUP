import random
import requests
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMessageBox
from qgis._core import QgsRasterLayer, QgsProject, QgsSettings, QgsMessageLog, Qgis

from ..utils import PluginDir, tianditu_map_url, TIANDITU_HOME_URL, TianMapInfo, PLUGIN_NAME, current_qgis_version, \
    check_crs, MESSAGE_TAG


def get_extra_map_icon(map_data: object):
    """获取额外地图的图标

    Args:
        map_data (object): 地图信息

    Returns:
        QIcon: 图标
    """
    # icon_home_path = PluginDir + "/icons/map_icons/"
    icon_home_path = ":/icons/map_icons/"
    if "icon" in map_data:
        icon = QIcon(icon_home_path + map_data["icon"])
    else:
        icon = QIcon(icon_home_path + "default.svg")
    return icon


def add_extra_map(map_data: object) -> None:
    """添加额外的地图

    Args:
        map_data (object): 地图信息
    """
    name = map_data["name"]
    uri = get_map_uri(
        map_data["url"], map_data["zmin"], map_data["zmax"], map_data["referer"]
    )
    add_xyz_layer(uri, name)


def add_xyz_layer(uri: str, name: str, providerType: str = "wms") -> None:
    """QGIS 添加xyz图层

    Args:
        uri (str): 图层uri
        name (str): 图层名称
        providerType(str): 类型(wms,arcgismapserver)
    """
    raster_layer = QgsRasterLayer(uri, name, providerType)
    QgsProject.instance().addMapLayer(raster_layer)


def get_map_uri(url: str, zmin: int = 0, zmax: int = 18, referer: str = "") -> str:
    """返回瓦片地图uri

    Args:
        url (str): 瓦片地图url
        zmin (int, optional): z 最小值. Defaults to 0.
        zmax (int, optional): z 最大值 Defaults to 18.
        referer (str, optional): Referer. Defaults to "".

    Returns:
        str: 瓦片地图uri
    """
    # ?" 进行 URL 编码后, 在 3.34 版本上无法加载地图
    # "&"是必须要进行 url 编码的
    url_quote = requests.utils.quote(url, safe=":/?=")
    uri = f"type=xyz&url={url_quote}&zmin={zmin}&zmax={zmax}"
    if referer != "":
        if current_qgis_version >= 32600:
            uri += f"&http-header:referer={referer}"
        else:
            uri += f"&referer={referer}"
    return uri


def add_tianditu_basemap(maptype, project, parent=None):
    crs = project.crs()
    if not check_crs(crs):
        QMessageBox.warning(None, '警告', '为了使用影像底图，请将当前坐标系统调整为web墨卡托投影(EPSG:3857)、'
                                        '国家大地2000投影(EPSG:4547)、国家大地2000经纬度(EPSG:4490)或者WGS84经纬度(EPSG:4326)',
                            QMessageBox.Ok)
    else:
        QgsMessageLog.logMessage("插件{}: 当前坐标系统{}, 符合输入要求.".format(PLUGIN_NAME, crs.authid()), tag=MESSAGE_TAG, level=Qgis.MessageLevel.Info)

    qset = QgsSettings()
    key = qset.value(f"{PLUGIN_NAME}/tianditu/key")
    keyisvalid = qset.value(f"{PLUGIN_NAME}/tianditu/keyisvalid", type=bool)
    # random_enabled = self.qset.value(f"{PLUGIN_NAME}Tianditu/random", type=bool)
    random_enabled = True
    subdomain = qset.value(f"{PLUGIN_NAME}/tianditu/subdomain")
    if key == "" or keyisvalid is False:
        QMessageBox.warning(
            parent, "错误", "天地图Key未设置或Key无效", QMessageBox.Yes, QMessageBox.Yes
        )
    else:
        if random_enabled:
            subdomain = random.choice(
                ["t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7"]
            )
            uri = get_map_uri(
                tianditu_map_url(maptype, key, subdomain),
                zmin=1,
                referer=TIANDITU_HOME_URL,
            )
        else:
            uri = get_map_uri(
                tianditu_map_url(maptype, key, subdomain),
                zmin=1,
                referer=TIANDITU_HOME_URL,
            )
        add_xyz_layer(uri, TianMapInfo[maptype])