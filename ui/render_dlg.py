# -*- coding: utf-8 -*-
"""
/***************************************************************************
 renderUPDialog
                                 A QGIS plugin
 编制方案渲染出图工具
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2023-12-28
        git sha              : $Format:%H$
        copyright            : (C) 2023 by mono zou
        email                : zou_mono@sina.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import logging
import os
import math

from PyQt5.QtCore import QEvent, QSize, QRegularExpression
from PyQt5.QtGui import QRegularExpressionValidator, QColor, QFont
from PyQt5.QtWidgets import QMessageBox
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis._core import QgsMessageLog, Qgis, QgsProject, QgsMapLayerType, QgsWkbTypes, QgsSymbol, QgsMarkerSymbol, \
    QgsLineSymbol, QgsFillSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer, QgsLineSymbolLayer, \
    QgsSimpleLineSymbolLayer, QgsSvgMarkerSymbolLayer, QgsSimpleMarkerSymbolLayer, QgsUnitTypes, QgsFillSymbolLayer, \
    QgsSimpleFillSymbolLayer, QgsSettings, QgsPalLayerSettings, QgsTextBufferSettings, QgsTextFormat, \
    QgsVectorLayerSimpleLabeling
from qgis._gui import QgisInterface

from .render_dlg_style import Ui_renderUPDialogBase
from ..utils import get_field_index_no_case, default_field, metro_line_color_dict, PluginDir, poi_type_color_dict, \
    get_qset_name, PLUGIN_NAME, check_crs, MESSAGE_TAG, get_default_font, PluginConfig, DefaultFont, default_label_size, \
    default_diag, default_metro_station_size, default_poi_size, default_block_outline_width, default_metro_network_width

log = logging.getLogger('QGIS')

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
# FORM_CLASS, _ = uic.loadUiType(os.path.join(
#     os.path.dirname(__file__), 'render_dlg_style.ui'))


# class renderDialog(QtWidgets.QDialog, FORM_CLASS):
class renderDialog(QtWidgets.QDialog, Ui_renderUPDialogBase):
    def __init__(self, iface: QgisInterface, parent=None):
        """Constructor."""
        super(renderDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.setFixedSize(QSize(480, 250))
        self.qset = QgsSettings()

        self.config = PluginConfig(
            key=self.qset.value(get_qset_name("key")),
            random_enabled=True,
            keyisvalid=self.qset.value(get_qset_name("keyisvalid"), type=bool),
            subdomain=self.qset.value(get_qset_name("subdomain")),
            extramap_enabled=True,
            lastpath=self.qset.value(get_qset_name("lastpath")),
            out_path=self.qset.value(get_qset_name("out_path")),
            out_width=self.qset.value(get_qset_name("out_width"), type=int),
            out_height=self.qset.value(get_qset_name("out_height"), type=int),
            out_resolution=self.qset.value(get_qset_name("out_resolution"), type=int),
            out_format=self.qset.value(get_qset_name("out_format"), type=str),
            draw_circle=self.qset.value(get_qset_name("draw_circle"), type=int),
            draw_northarrow=self.qset.value(get_qset_name("draw_northarrow"), type=int),
            draw_scalebar=self.qset.value(get_qset_name("draw_scalebar"), type=int),
            draw_legend=self.qset.value(get_qset_name("draw_legend"), type=int),
            radius=self.qset.value(get_qset_name("radius"), type=float)
        )

        self.iface = iface
        self.project: QgsProject = QgsProject.instance()
        self.qset = QgsSettings()

        self.lbl_radius.setVisible(False)
        self.txt_radius.setVisible(False)
        self.ckb_draw_circle.setCheckState(False)

        reg = QRegularExpression(r"^(0*[1-9][0-9]*(\.[0-9]+)?|0+\.[0-9]*[1-9][0-9]*)$")
        doubleValidator = QRegularExpressionValidator()
        doubleValidator.setRegularExpression(reg)
        self.txt_radius.setValidator(doubleValidator)

        self.cmb_image_layer.installEventFilter(self)
        self.cmb_metro_network_layer.installEventFilter(self)
        self.cmb_metro_station_layer.installEventFilter(self)
        self.cmb_poi_layer.installEventFilter(self)
        self.cmb_block_layer.installEventFilter(self)
        self.cmb_block_layer.currentIndexChanged.connect(self.block_layer_changed)
        self.cmb_poi_layer.currentIndexChanged.connect(self.poi_layer_changed)
        self.cmb_metro_station_layer.currentIndexChanged.connect(self.metro_station_layer_changed)
        self.cmb_image_layer.currentIndexChanged.connect(self.image_layer_changed)

        self.ckb_draw_circle.stateChanged.connect(self.enable_draw_circle)
        self.ckb_draw_northarrow.stateChanged.connect(self.enable_draw_northarrow)
        self.ckb_draw_scalebar.stateChanged.connect(self.enable_draw_scalebar)
        self.ckb_draw_legend.stateChanged.connect(self.enable_draw_legend)
        self.ckb_draw_circle.setCheckState(self.config.draw_circle)
        self.ckb_draw_northarrow.setCheckState(self.config.draw_northarrow)
        self.ckb_draw_scalebar.setCheckState(self.config.draw_scalebar)
        self.ckb_draw_legend.setCheckState(self.config.draw_legend)

        self.btn_default.clicked.connect(self.btn_default_clicked)
        self.txt_radius.textChanged.connect(self.on_txt_radius_changed)

        # self.btn_cancel.clicked.connect(self.btn_cancel_clicked)

        # eventFilter = escapeEventFilter(self)
        # self.installEventFilter(eventFilter)

    def btn_cancel_clicked(self):
        self.close()

    def show(self) -> None:
        self.init_cmb_layers()

        ids = [layer.id() for layer in self.project.mapLayers().values()]

        image_layer_id = self.qset.value(get_qset_name('image_layer_id'))
        if image_layer_id in ids:
            self.cmb_image_layer.setCurrentText(self.project.mapLayer(image_layer_id).name())

        metro_network_layer_id = self.qset.value(get_qset_name('metro_network_layer_id'))
        if metro_network_layer_id in ids:
            self.cmb_metro_network_layer.setCurrentText(self.project.mapLayer(metro_network_layer_id).name())

        metro_station_layer_id = self.qset.value(get_qset_name('metro_station_layer_id'))
        if metro_station_layer_id in ids:
            self.cmb_metro_station_layer.setCurrentText(self.project.mapLayer(metro_station_layer_id).name())

        poi_layer_id = self.qset.value(get_qset_name('poi_layer_id'))
        if poi_layer_id in ids:
            self.cmb_poi_layer.setCurrentText(self.project.mapLayer(poi_layer_id).name())

        block_layer_id = self.qset.value(get_qset_name('block_layer_id'))
        if block_layer_id in ids:
            self.cmb_block_layer.setCurrentText(self.project.mapLayer(block_layer_id).name())

        super(renderDialog, self).show()

    def eventFilter(self,target,event):
        if event.type() == QEvent.MouseButtonPress:
            if target == self.cmb_image_layer:
                self.cmb_pressed('image')
            elif target == self.cmb_metro_network_layer:
                self.cmb_pressed('network')
            elif target == self.cmb_poi_layer:
                self.cmb_pressed('poi')
            elif target == self.cmb_metro_station_layer:
                self.cmb_pressed('station')
            elif target == self.cmb_block_layer:
                self.cmb_pressed('block')
        return super().eventFilter(target, event)

    def init_cmb_layers(self, cname=None):
        if self.project.mapLayers() is None:
            return

        if cname is None:
            self.cmb_image_layer.clear()
            self.cmb_metro_network_layer.clear()
            self.cmb_metro_station_layer.clear()
            self.cmb_poi_layer.clear()
            self.cmb_block_layer.clear()

            self.cmb_image_layer.addItem("")
            self.cmb_metro_network_layer.addItem("")
            self.cmb_metro_station_layer.addItem("")
            self.cmb_poi_layer.addItem("")
            self.cmb_block_layer.addItem("")

            for layer in self.project.mapLayers().values():
                node = self.project.layerTreeRoot().findLayer(layer.id())
                if layer.type() == QgsMapLayerType.RasterLayer and node.isVisible():
                    # layer_names_ras.append(layer.name())
                    self.cmb_image_layer.addItem(layer.name(), layer.id())
                elif layer.type() == QgsMapLayerType.VectorLayer and node.isVisible() and \
                        layer.geometryType() == QgsWkbTypes.GeometryType.LineGeometry:
                    self.cmb_metro_network_layer.addItem(layer.name(), layer.id())
                elif layer.type() == QgsMapLayerType.VectorLayer and node.isVisible() and \
                        layer.geometryType() == QgsWkbTypes.GeometryType.PointGeometry:
                    self.cmb_metro_station_layer.addItem(layer.name(), layer.id())
                    self.cmb_poi_layer.addItem(layer.name(), layer.id())
                elif layer.type() == QgsMapLayerType.VectorLayer and node.isVisible() and \
                        layer.geometryType() == QgsWkbTypes.GeometryType.PolygonGeometry:
                    self.cmb_block_layer.addItem(layer.name(), layer.id())
        elif cname == 'image':
            self.cmb_image_layer.clear()
            self.cmb_image_layer.addItem("")
            for layer in self.project.mapLayers().values():
                node = self.project.layerTreeRoot().findLayer(layer.id())
                if layer.type() == QgsMapLayerType.RasterLayer and node.isVisible():
                    self.cmb_image_layer.addItem(layer.name(), layer.id())
        elif cname == 'network':
            self.cmb_metro_network_layer.clear()
            self.cmb_metro_network_layer.addItem("")
            for layer in self.project.mapLayers().values():
                node = self.project.layerTreeRoot().findLayer(layer.id())
                if layer.type() == QgsMapLayerType.VectorLayer and node.isVisible():
                    if layer.geometryType() == QgsWkbTypes.GeometryType.LineGeometry:
                        self.cmb_metro_network_layer.addItem(layer.name(), layer.id())
        elif cname == 'poi':
            self.cmb_poi_layer.clear()
            self.cmb_poi_layer.addItem("")
            for layer in self.project.mapLayers().values():
                node = self.project.layerTreeRoot().findLayer(layer.id())
                if layer.type() == QgsMapLayerType.VectorLayer and node.isVisible():
                    if layer.geometryType() == QgsWkbTypes.GeometryType.PointGeometry:
                        self.cmb_poi_layer.addItem(layer.name(), layer.id())
        elif cname == 'station':
            self.cmb_metro_station_layer.clear()
            self.cmb_metro_station_layer.addItem("")
            for layer in self.project.mapLayers().values():
                node = self.project.layerTreeRoot().findLayer(layer.id())
                if layer.type() == QgsMapLayerType.VectorLayer and node.isVisible():
                    if layer.geometryType() == QgsWkbTypes.GeometryType.PointGeometry:
                        self.cmb_metro_station_layer.addItem(layer.name(), layer.id())
        elif cname == 'block':
            self.cmb_block_layer.clear()
            self.cmb_block_layer.addItem("")
            for layer in self.project.mapLayers().values():
                node = self.project.layerTreeRoot().findLayer(layer.id())
                if layer.type() == QgsMapLayerType.VectorLayer and node.isVisible():
                    if layer.geometryType() == QgsWkbTypes.GeometryType.PolygonGeometry:
                        self.cmb_block_layer.addItem(layer.name(), layer.id())

    def cmb_pressed(self, cname):
        # QgsMessageLog.logMessage("changed", tag="Plugins", level=Qgis.MessageLevel.Warning)
        self.init_cmb_layers(cname)

    def block_layer_changed(self, index):
        self.current_block_layer_id = self.cmb_block_layer.itemData(index)
        layer = self.project.mapLayer(self.current_block_layer_id)
        if layer is None:
            return

        if not check_crs(layer.crs()):
            QMessageBox.warning(self, '警告', '请为地块图层设置有效的坐标系统(web墨卡托投影(EPSG:3857)、'
                                            '国家大地2000投影(EPSG:4547)、国家大地2000经纬度(EPSG:4490)或者WGS84经纬度(EPSG:4326))',
                                QMessageBox.Ok)
        self.qset.setValue(get_qset_name("block_layer_id"), self.current_block_layer_id)

    def poi_layer_changed(self, index):
        self.current_poi_layer_id = self.cmb_poi_layer.itemData(index)
        layer = self.project.mapLayer(self.current_poi_layer_id)
        if layer is None:
            return
        self.qset.setValue(get_qset_name("poi_layer_id"), self.current_poi_layer_id)

    def metro_station_layer_changed(self, index):
        self.current_metro_station_layer_id = self.cmb_metro_station_layer.itemData(index)
        layer = self.project.mapLayer(self.current_metro_station_layer_id)
        if layer is None:
            return
        self.qset.setValue(get_qset_name("metro_station_layer_id"), self.current_metro_station_layer_id)

    def image_layer_changed(self, index):
        self.current_image_layer_id = self.cmb_image_layer.itemData(index)
        layer = self.project.mapLayer(self.current_image_layer_id)
        if layer is None:
            return
        self.qset.setValue(get_qset_name("image_layer_id"), self.current_image_layer_id)

    def btn_default_clicked(self):
        layer_image_id = self.cmb_image_layer.itemData(self.cmb_image_layer.currentIndex())
        layer_metro_network_id = self.cmb_metro_network_layer.itemData(self.cmb_metro_network_layer.currentIndex())
        layer_metro_station_id = self.cmb_metro_station_layer.itemData(self.cmb_metro_station_layer.currentIndex())
        layer_poi_id = self.cmb_poi_layer.itemData(self.cmb_poi_layer.currentIndex())
        layer_block_id = self.cmb_block_layer.itemData(self.cmb_block_layer.currentIndex())

        out_width = float(self.qset.value(get_qset_name("out_width")))
        out_height = float(self.qset.value(get_qset_name("out_height")))
        out_resolution = float(self.qset.value(get_qset_name("out_resolution")))

        out_diag = math.sqrt(out_width ** 2 + out_height ** 2)
        label_size = int(out_diag * default_label_size * 72 / out_resolution)
        metro_station_size = out_diag * default_metro_station_size

        self.render_mertro_network(layer_metro_network_id, int(out_diag * default_metro_network_width))
        self.render_metro_station(layer_metro_station_id, int(metro_station_size), int(label_size * 1.5))
        self.render_poi(layer_poi_id, int(out_diag * default_poi_size), label_size)
        self.render_block(layer_block_id, int(out_diag * default_block_outline_width))
        self.render_image(layer_image_id)

    def render_image(self, layer_image_id):
        if layer_image_id is not None:
            layer = self.project.mapLayer(layer_image_id)
            layer.renderer().setOpacity(0.5)
            layer.triggerRepaint()
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())

    def render_block(self, layer_block_id, default_width=5):
        if layer_block_id is not None:
            layer = self.project.mapLayer(layer_block_id)
            # symbol = QgsFillSymbolLayer()
            symbol = QgsSimpleFillSymbolLayer.create({
                'outline_color': "#C00000",
                'color': "#FF0066",
                'outline_width': f"{default_width}",
                'outline_width_unit': 'Pixel'
            })
            layer.renderer().symbol().changeSymbolLayer(0, symbol)
            layer.triggerRepaint()
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())

    def render_poi(self, layer_poi_id, default_size, default_outline_size, defalut_font_size=8):
        if layer_poi_id is not None:
            layer = self.project.mapLayer(layer_poi_id)
            fni, field_name = get_field_index_no_case(layer, default_field.name_poi_type)

            if fni < 0:
                QgsMessageLog.logMessage(f"插件{PLUGIN_NAME}:字段type不存在,无法自动配色.", tag=MESSAGE_TAG, level=Qgis.MessageLevel.Warning)
                return

            poi_type_dict = {}
            spec_dict = {}
            for fea in layer.getFeatures():
                poi_type = str(fea.attributes()[fni])
                # poi_name_dict[poi_name] = poi_name
                poi_type_dict[poi_type] = poi_type
                if poi_type in poi_type_color_dict:
                    symbol_layer = QgsSimpleMarkerSymbolLayer.create({
                        'color': poi_type_color_dict[poi_type],
                        'size': f"{default_size}",
                        'outline_color': '#ffffff',
                        'outline_width': f'{default_outline_size}',
                        'outline_width_unit': "Pixel",
                        'size_unit': "Pixel"
                        # 'outline_color': metro_line_color_dict[lineid],
                    })

                    spec_dict[poi_type] = symbol_layer

            categrorized_renderer(layer, fni, poi_type_dict, field_name, spec_dict=spec_dict)
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())

            fni, field_name = get_field_index_no_case(layer, default_field.name_poi)
            self.set_label(layer, field_name, font_size=defalut_font_size)

    def render_metro_station(self, layer_metro_station_id, default_size=15, default_label_size=12):
        if layer_metro_station_id is not None:
            layer = self.project.mapLayer(layer_metro_station_id)
            symbol = QgsSvgMarkerSymbolLayer(os.path.join(PluginDir, "icons/metro_station.svg"))
            if symbol is not None:
                symbol.setSize(default_size)
                symbol.setSizeUnit(QgsUnitTypes.RenderUnit.RenderPixels)
                layer.renderer().symbol().changeSymbolLayer(0, symbol)
            layer.triggerRepaint()
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())

            fni, field_name = get_field_index_no_case(layer, default_field.name_metro_station_name)
            self.set_label(layer, field_name, font_size=default_label_size, has_buffer=False)

    def render_mertro_network(self, layer_metro_network_id, default_width):
        if layer_metro_network_id is not None:
            layer = self.project.mapLayer(layer_metro_network_id)
            fni, field_name = get_field_index_no_case(layer, default_field.name_metro_line_id)

            if fni < 0:
                QgsMessageLog.logMessage(f"插件{PLUGIN_NAME}:字段lineID不存在,无法自动配色.", tag=MESSAGE_TAG, level=Qgis.MessageLevel.Warning)
                return

            network_type = {}
            spec_dict = {}
            for fea in layer.getFeatures():
                lineid = str(fea.attributes()[fni])
                network_type[lineid] = f"{lineid}号线"
                symbol_layer = QgsSimpleLineSymbolLayer.create({
                    'color': metro_line_color_dict[lineid],
                    'line_width': f'{default_width}',
                    'line_width_unit': 'Pixel'
                    # 'outline_color': metro_line_color_dict[lineid],
                })
                spec_dict[lineid] = symbol_layer

            categrorized_renderer(layer, fni, network_type, field_name, spec_dict=spec_dict)
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())

    def set_label(self, layer, field_name, font_size=10, has_buffer=True):
        layer_settings = QgsPalLayerSettings()
        text_format = QgsTextFormat()
        text_format.setFont(QFont(DefaultFont, font_size))
        text_format.setSize(font_size)

        if has_buffer:
            buffer_settings = QgsTextBufferSettings()
            buffer_settings.setEnabled(True)
            buffer_settings.setSize(1)
            buffer_settings.setColor(QColor("white"))
            text_format.setBuffer(buffer_settings)

        layer_settings.setFormat(text_format)
        layer_settings.fieldName = field_name
        layer_settings.placement = Qgis.LabelPlacement.AroundPoint

        layer_settings.enabled = True

        layer_settings = QgsVectorLayerSimpleLabeling(layer_settings)
        layer.setLabelsEnabled(True)
        layer.setLabeling(layer_settings)
        layer.triggerRepaint()

    def enable_draw_circle(self):
        if self.ckb_draw_circle.isChecked():
            self.qset.setValue(get_qset_name("draw_circle"), True)
            self.lbl_radius.setVisible(True)
            self.txt_radius.setVisible(True)
            self.txt_radius.setText(str(self.qset.value(get_qset_name("radius"))))
        else:
            self.qset.setValue(get_qset_name("draw_circle"), False)
            self.lbl_radius.setVisible(False)
            self.txt_radius.setVisible(False)

    def enable_draw_northarrow(self):
        if self.ckb_draw_northarrow.isChecked():
            self.qset.setValue(get_qset_name("draw_northarrow"), True)
        else:
            self.qset.setValue(get_qset_name("draw_northarrow"), False)

    def enable_draw_scalebar(self):
        if self.ckb_draw_scalebar.isChecked():
            self.qset.setValue(get_qset_name("draw_scalebar"), True)
        else:
            self.qset.setValue(get_qset_name("draw_scalebar"), False)

    def enable_draw_legend(self):
        if self.ckb_draw_legend.isChecked():
            self.qset.setValue(get_qset_name("draw_legend"), True)
        else:
            self.qset.setValue(get_qset_name("draw_legend"), False)

    def on_txt_radius_changed(self):
        if self.txt_radius.text() == "":
            return
        self.qset.setValue(get_qset_name("radius"), float(self.txt_radius.text()))


def validatedDefaultSymbol(geometryType):
    symbol = QgsSymbol.defaultSymbol(geometryType)
    if symbol is None:
        if geometryType == QgsWkbTypes.GeometryType.PointGeometry:
            symbol = QgsMarkerSymbol()
        elif geometryType == QgsWkbTypes.GeometryType.LineGeometry:
            symbol = QgsLineSymbol()
        elif geometryType == QgsWkbTypes.GeometryType.PolygonGeometry:
            symbol = QgsFillSymbol()
    return symbol


def categrorized_renderer(layer, index, data, render_field, color_ramp=None, spec_dict=None):
    unique_values = layer.uniqueValues(index)

    # fill categories
    categories = []
    for unique_value in unique_values:
        symbol = None

        unique_value = str(unique_value)

        # initialize the default symbol for this geometry type
        symbol = validatedDefaultSymbol(layer.geometryType())
        if spec_dict is not None:
            # QgsMessageLog.logMessage(str(spec_dict))
            if unique_value in spec_dict:
                symbol_layer = spec_dict[unique_value]
                symbol.changeSymbolLayer(0, symbol_layer)

        # create renderer object
        if unique_value in data:
            category = QgsRendererCategory(unique_value, symbol, data[unique_value])
        else:
            category = QgsRendererCategory(unique_value, symbol, str(unique_value))
        # entry for the list of category items
        categories.append(category)

    renderer = QgsCategorizedSymbolRenderer(render_field, categories)
    if color_ramp is not None:
        renderer.updateColorRamp(color_ramp)
    if renderer is not None:
        layer.setRenderer(renderer)
        layer.triggerRepaint()
