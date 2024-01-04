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

from PyQt5.QtCore import QEvent, QSize, QRegularExpression
from PyQt5.QtGui import QRegularExpressionValidator
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis._core import QgsMessageLog, Qgis, QgsProject, QgsMapLayerType, QgsWkbTypes, QgsSymbol, QgsMarkerSymbol, \
    QgsLineSymbol, QgsFillSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer, QgsLineSymbolLayer, \
    QgsSimpleLineSymbolLayer, QgsSvgMarkerSymbolLayer, QgsSimpleMarkerSymbolLayer, QgsUnitTypes, QgsFillSymbolLayer, \
    QgsSimpleFillSymbolLayer, QgsSettings
from qgis._gui import QgisInterface

from ..utils import get_field_index_no_case, default_field, metro_line_color_dict, PluginDir, poi_type_color_dict, \
    get_qset_name, PLUGIN_NAME

log = logging.getLogger('QGIS')

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'render_dlg_style.ui'))


class renderDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, iface: QgisInterface, parent=None):
        """Constructor."""
        super(renderDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.setFixedSize(QSize(480, 300))

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

        self.ckb_draw_circle.stateChanged.connect(self.enable_draw_circle)
        self.btn_default.clicked.connect(self.btn_default_clicked)
        self.txt_radius.textChanged.connect(self.on_txt_radius_changed)

    def show(self) -> None:
        self.init_cmb_layers()
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

        return False

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
                    self.cmb_block_layer.addItem("")

            # self.cmb_image_layer.addItems(layer_names_ras)
            # self.cmb_metro_network_layer.addItems(layer_names_vec_polyline)
            # self.cmb_metro_station_layer.addItems(layer_names_vec_point)
            # self.cmb_poi_layer.addItems(layer_names_vec_point)
            # self.cmb_block_layer.addItems(layer_names_vec_polygon)

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
                if layer.type() == QgsMapLayerType.VectorLayer:
                    if layer.geometryType() == QgsWkbTypes.GeometryType.PointGeometry:
                        self.cmb_poi_layer.addItem(layer.name(), layer.id())
        elif cname == 'station':
            self.cmb_metro_station_layer.clear()
            self.cmb_metro_station_layer.addItem("")
            for layer in self.project.mapLayers().values():
                if layer.type() == QgsMapLayerType.VectorLayer:
                    if layer.geometryType() == QgsWkbTypes.GeometryType.PointGeometry:
                        self.cmb_metro_station_layer.addItem(layer.name(), layer.id())
        elif cname == 'block':
            self.cmb_block_layer.clear()
            self.cmb_block_layer.addItem("")
            for layer in self.project.mapLayers().values():
                if layer.type() == QgsMapLayerType.VectorLayer:
                    if layer.geometryType() == QgsWkbTypes.GeometryType.PolygonGeometry:
                        self.cmb_block_layer.addItem(layer.name(), layer.id())

    def cmb_pressed(self, cname):
        # QgsMessageLog.logMessage("changed", tag="Plugins", level=Qgis.MessageLevel.Warning)
        self.init_cmb_layers(cname)

    def block_layer_changed(self, index):
        self.current_block_layer_id = self.cmb_block_layer.itemData(index)
        self.qset.setValue(get_qset_name("block_layer_id"), self.current_block_layer_id)

    def btn_default_clicked(self):
        layer_image_id = self.cmb_image_layer.itemData(self.cmb_image_layer.currentIndex())
        layer_metro_network_id = self.cmb_metro_network_layer.itemData(self.cmb_metro_network_layer.currentIndex())
        layer_metro_station_id = self.cmb_metro_station_layer.itemData(self.cmb_metro_station_layer.currentIndex())
        layer_poi_id = self.cmb_poi_layer.itemData(self.cmb_poi_layer.currentIndex())
        layer_block_id = self.cmb_block_layer.itemData(self.cmb_block_layer.currentIndex())

        self.render_mertro_network(layer_metro_network_id)
        self.render_metro_station(layer_metro_station_id)
        self.render_poi(layer_poi_id)
        self.render_block(layer_block_id)
        self.render_image(layer_image_id)

    def render_image(self, layer_image_id):
        if layer_image_id is not None:
            layer = self.project.mapLayer(layer_image_id)
            layer.renderer().setOpacity(0.5)
            layer.triggerRepaint()
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())

    def render_block(self, layer_block_id):
        if layer_block_id is not None:
            layer = self.project.mapLayer(layer_block_id)
            # symbol = QgsFillSymbolLayer()
            symbol = QgsSimpleFillSymbolLayer.create({
                'outline_color': "#C00000",
                'color': "#FF0066",
                'outline_width': "5",
                'outline_width_unit': 'Pixel'
            })
            layer.renderer().symbol().changeSymbolLayer(0, symbol)
            layer.triggerRepaint()
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())

    def render_poi(self, layer_poi_id):
        if layer_poi_id is not None:
            layer = self.project.mapLayer(layer_poi_id)
            fni, field_name = get_field_index_no_case(layer, default_field.name_poi_type)

            poi_type_dict = {}
            spec_dict = {}
            for fea in layer.getFeatures():
                poi_type = str(fea.attributes()[fni])
                # poi_name_dict[poi_name] = poi_name
                poi_type_dict[poi_type] = poi_type
                if poi_type in poi_type_color_dict:
                    symbol_layer = QgsSimpleMarkerSymbolLayer.create({
                        'color': poi_type_color_dict[poi_type],
                        'size': '4',
                        'outline_color': '#ffffff',
                        'outline_width': '1'
                        # 'outline_color': metro_line_color_dict[lineid],
                    })

                    spec_dict[poi_type] = symbol_layer

            categrorized_renderer(layer, fni, poi_type_dict, field_name, spec_dict=spec_dict)
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())

    def render_metro_station(self, layer_metro_station_id):
        if layer_metro_station_id is not None:
            layer = self.project.mapLayer(layer_metro_station_id)
            symbol = QgsSvgMarkerSymbolLayer(os.path.join(PluginDir, "icons/metro_station.svg"))
            if symbol is not None:
                symbol.setSize(15)
                symbol.setSizeUnit(QgsUnitTypes.RenderUnit.RenderPoints)
                layer.renderer().symbol().changeSymbolLayer(0, symbol)
            layer.triggerRepaint()
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())

    def render_mertro_network(self, layer_metro_network_id):
        if layer_metro_network_id is not None:
            layer = self.project.mapLayer(layer_metro_network_id)
            fni, field_name = get_field_index_no_case(layer, default_field.name_metro_line_id)

            network_type = {}
            spec_dict = {}
            for fea in layer.getFeatures():
                lineid = str(fea.attributes()[fni])
                network_type[lineid] = f"{lineid}号线"
                symbol_layer = QgsSimpleLineSymbolLayer.create({
                    'color': metro_line_color_dict[lineid],
                    'line_width': '6',
                    'line_width_unit': 'Points'
                    # 'outline_color': metro_line_color_dict[lineid],
                })
                spec_dict[lineid] = symbol_layer

            categrorized_renderer(layer, fni, network_type, field_name, spec_dict=spec_dict)
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())

    def enable_draw_circle(self):
        if self.ckb_draw_circle.isChecked():
            self.qset.setValue(f"{PLUGIN_NAME}/extra/draw_circle", True)
            self.lbl_radius.setVisible(True)
            self.txt_radius.setVisible(True)
        else:
            self.qset.setValue(f"{PLUGIN_NAME}/extra/draw_circle", False)
            self.lbl_radius.setVisible(False)
            self.txt_radius.setVisible(False)

    def on_txt_radius_changed(self):
        if self.txt_radius.text() == "":
            return
        self.qset.setValue(f"{PLUGIN_NAME}/extra/radius", float(self.txt_radius.text()))


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
