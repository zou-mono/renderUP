import math
import os.path
import random
import time
import traceback

from PyQt5.QtCore import QTimer, QSize, QSizeF, QPoint, Qt, QPointF, QEvent
from PyQt5.QtGui import QPainter, QImage, QColor, QFont, QTextFormat
from PyQt5.QtWidgets import QMessageBox
from osgeo.osr import SpatialReference
from qgis.PyQt import QtCore
from qgis._core import QgsMapSettings, QgsSettings, QgsProject, QgsMessageLog, Qgis, QgsMapLayerType, \
    QgsMapRendererCustomPainterJob, QgsMapRendererParallelJob, QgsMapRendererSequentialJob, QgsPrintLayout, \
    QgsLayoutItemMap, QgsLayoutPoint, QgsUnitTypes, QgsLayoutSize, QgsLayoutExporter, QgsRectangle, QgsLayoutItemPage, \
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsDistanceArea, QgsCoordinateTransformContext, \
    QgsLayoutItemShape, QgsSimpleFillSymbolLayer, QgsFillSymbol, QgsLayoutItem, QgsMapToPixel, QgsTask, QgsApplication, \
    QgsLayoutItemPicture, QgsLayoutItemScaleBar, QgsScaleBarSettings, QgsLayoutItemLegend, QgsLegendStyle, QgsLayerTree, \
    QgsLegendRenderer, QgsTextFormat
from qgis._gui import QgisInterface

from ..utils import get_qset_name, get_field_index_no_case, default_field, ExportDir, epsg_code, PluginConfig, \
    MESSAGE_TAG, IconDir, DefaultFont, default_scalebar_size, default_diag


# class escapeEventFilter(QtCore.QObject):
#     def __init__(self, parent=None):
#         super(escapeEventFilter, self).__init__(parent)
#
#     def eventFilter(self, obj: QtCore.QObject, event):
#         if event.type() == QEvent.KeyRelease:
#             # QMessageBox.information(None, 'MyEventFilter', f'event: {event}')
#             # QgsMessageLog.logMessage("escape key pressed", tag=MESSAGE_TAG, level=Qgis.MessageLevel.Warning)
#             if event.key() == Qt.Key_B:
#                 QgsMessageLog.logMessage("escape B pressed", tag=MESSAGE_TAG, level=Qgis.MessageLevel.Warning)
#                 return True
#         return False


class bacth_export(QgsTask):
    def __init__(self, description, iface: QgisInterface, block_layer):
        super(bacth_export, self).__init__(description)
        self.qset = QgsSettings()
        self.block_layer = block_layer
        self.iface = iface
        self.project = QgsProject.instance()
        iface.mainWindow().keyPressed.connect(self.key_pressed)
        iface.mapCanvas().keyPressed.connect(self.key_pressed)
        self.exception = None

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

    def key_pressed(self, event):
        if event.key() == Qt.Key_Escape:
            self.cancel()

    def run(self):
        out_width = self.config.out_width
        out_height = self.config.out_height
        out_resolution = self.config.out_resolution
        out_format = self.config.out_format
        draw_circle = self.config.draw_circle
        draw_northarrow = self.config.draw_northarrow
        draw_scalebar = self.config.draw_scalebar
        draw_legend = self.config.draw_legend
        radius = self.config.radius
        out_path = os.path.join(self.config.out_path)

        out_diag = math.sqrt(out_width ** 2 + out_height ** 2)
        scalebar_size = int(out_diag * default_scalebar_size * 72 / out_resolution)
        legend_title_size = int(scalebar_size * 1.5)
        legend_label_size = int(legend_title_size * 0.8)
        # QgsMessageLog.logMessage("大小:{}".format(scalebar_size), tag="Plugins",
        #                          level=Qgis.MessageLevel.Info)

        try:
            metro_station_layer_id = self.qset.value(get_qset_name("metro_station_layer_id"))
            poi_layer_id = self.qset.value(get_qset_name("poi_layer_id"))
            checked_layer_ids = {
                "轨道站点": metro_station_layer_id,
                "POI": poi_layer_id
            }

            lyrsToRemove = [l for l in self.project.mapLayers() if l not in list(checked_layer_ids.values())]

            # QgsMessageLog.logMessage(str(self.project.mapLayers()), tag="Plugins",
            #                          level=Qgis.MessageLevel.Info)

            circle_symbol_layer = QgsSimpleFillSymbolLayer.create({
                'outline_color': "64,64,64,77",
                'color': '0,0,0,0',
                'outline_style': 'dot',
                'outline_width': "5",
                'outline_width_unit': 'Pixel'
            })
            circle_symbol = QgsFillSymbol()
            circle_symbol.changeSymbolLayer(0, circle_symbol_layer)

            # lyrs_exist = [l for l in QgsProject().instance().layerTreeRoot().children() if l.isVisible()]

            # proj_id = self.project.crs().authid()
            if self.project.crs().isGeographic():
                self.project.setCrs(QgsCoordinateReferenceSystem("EPSG:3857"))

            bTransfer = False
            if self.block_layer.crs().isValid():
                if self.block_layer.crs().authid() != "EPSG:3857":
                    sourceCrs = QgsCoordinateReferenceSystem(f"EPSG:{epsg_code(self.block_layer.crs())}")
                    destCrs = QgsCoordinateReferenceSystem(f"EPSG:{epsg_code(self.project.crs())}")
                    geom_tr = QgsCoordinateTransform(sourceCrs, destCrs, self.project)
                    bTransfer = True
            else:
                raise Exception("地块图层坐标系统不符合标准.")

            self.block_layer.setSubsetString("")
            fids = []
            for fea in self.block_layer.getFeatures():
                fids.append(fea.id())

            ifeat = 1
            total_num = self.block_layer.featureCount()

            fid_name = self.get_key_column()

            # for feature in self.block_layer.getFeatures():
            for fea_id in fids:
                bflag = self.block_layer.setSubsetString("{}={}".format(fid_name, fea_id))
                # fea_id = str(feature.id())
                if not bflag:
                    QgsMessageLog.logMessage("fid{}不存在".format(fea_id), tag="Plugins",
                                             level=Qgis.MessageLevel.Warning)
                    self.setProgress(float(ifeat * 100 / total_num))
                    ifeat += 1
                    continue

                feature = next(self.block_layer.getFeatures())

                geom = feature.geometry()
                project_name = os.path.join(out_path, "project_files", f"{fea_id}.qgs")

                layoutName = "renderUP_layout"
                manager = self.project.layoutManager()
                layouts_list = manager.printLayouts()
                # remove any duplicate layouts
                for layout in layouts_list:
                    if layout.name() == layoutName:
                        manager.removeLayout(layout)

                layout = QgsPrintLayout(self.project)
                layout.initializeDefaults()
                layout.setName(layoutName)
                self.project.layoutManager().addLayout(layout)
                pc = layout.pageCollection()
                pc.pages()[0].setPageSize(QgsLayoutSize(out_width, out_height, QgsUnitTypes.LayoutUnit.LayoutPixels))

                map_item = self.draw_layout_mapitem(layout, out_width, out_height, out_resolution)

                # if self.block_layer.crs().isValid():
                #     # if self.block_layer.crs().isGeographic():
                #     if self.block_layer.crs().authid() != "EPSG:3857":
                if bTransfer:
                    geom.transform(geom_tr)
                    # sourceCrs = QgsCoordinateReferenceSystem(epsg_code(self.block_layer.crs()))
                    # destCrs = QgsCoordinateReferenceSystem(epsg_code(self.project.crs()))
                    #
                    # if sourceCrs != destCrs:
                    #     tr = QgsCoordinateTransform(sourceCrs, destCrs, self.project)
                    #     geom.transform(tr)

                centroid = geom.pointOnSurface().asPoint()
                # QgsMessageLog.logMessage("中心点坐标:{},{}".format(centroid.x(), centroid.y()), tag="Plugins",
                #                          level=Qgis.MessageLevel.Info)
                extent = QgsRectangle.fromCenterAndSize(centroid, 2 * radius, 2 * radius)
                extent.scale(1.2)
                map_item.zoomToExtent(extent)

                if self.isCanceled():
                    return False

                if draw_circle:
                    ele_circle = QgsLayoutItemShape(layout)
                    ele_circle.setShapeType(QgsLayoutItemShape.Shape.Ellipse)
                    ele_circle.setReferencePoint(QgsLayoutItem.ReferencePoint.Middle)
                    ele_circle.setSymbol(circle_symbol)

                    layout_centroid = map_item.mapToItemCoords(QPointF(centroid.x(), centroid.y()))
                    layout_radius = self.layout_length(map_item, radius, centroid)

                    ele_circle.attemptMove(QgsLayoutPoint(layout_centroid.x(), layout_centroid.y(), QgsUnitTypes.LayoutUnit.LayoutMillimeters))
                    ele_circle.setFixedSize(QgsLayoutSize(2 * layout_radius, 2 * layout_radius))
                    layout.addLayoutItem(ele_circle)

                if draw_northarrow:
                    north_path = os.path.join(IconDir, "north_arrow.svg")

                    if not os.path.exists(north_path):
                        north_path = os.path.join(QgsApplication.prefixPath(), "svg", "arrows", "NorthArrow_10.svg")
                        if not os.path.exists(north_path):
                            north_path = None

                    if north_path is not None:
                        out_north_width = 20 if out_width / 10 < 20 else int(out_width / 10)
                        out_north_height = 20 if out_height / 10 < 20 else int(out_height / 10)

                        north_item = QgsLayoutItemPicture(layout)
                        north_item.setPicturePath(north_path)
                        layout.addLayoutItem(north_item)
                        north_item.attemptResize(QgsLayoutSize(out_north_width, out_north_height, QgsUnitTypes.LayoutUnit.LayoutPixels))
                        north_item.attemptMove(QgsLayoutPoint(int(17 * out_width / 19), int(2 * out_height / 19), QgsUnitTypes.LayoutUnit.LayoutPixels))

                if draw_scalebar:
                    scalebar_item = QgsLayoutItemScaleBar(layout)
                    scalebar_item.setLinkedMap(map_item)
                    scalebar_item.setStyle("Line Ticks Up")
                    scalebar_item.attemptMove(QgsLayoutPoint(int(1 * out_width / 19), int(16 * out_height / 19), QgsUnitTypes.LayoutUnit.LayoutPixels))
                    scalebar_item.setUnitLabel("米")

                    tf = QgsTextFormat()
                    tf.setFont(QFont(DefaultFont))
                    tf.setSize(scalebar_size)
                    scalebar_item.setTextFormat(tf)
                    scalebar_item.setLabelBarSpace(1)  # 文字和标尺的空间，单位毫米

                    scalebar_item.setSegmentSizeMode(QgsScaleBarSettings.SegmentSizeMode.SegmentSizeFixed)
                    scalebar_item.setNumberOfSegmentsLeft(0)
                    scalebar_item.setNumberOfSegments(2)
                    scalebar_item.setMaximumBarWidth(40)
                    scalebar_item.setMinimumSize(QgsLayoutSize(40, 1.5))
                    scalebar_item.setUnits(QgsUnitTypes.DistanceUnit.DistanceMeters)
                    scalebar_item.setUnitsPerSegment(int(radius / 4))
                    scalebar_item.setHeight(out_height / 500)

                    layout.addLayoutItem(scalebar_item)

                if draw_legend:
                    legend_item = QgsLayoutItemLegend(layout)
                    legend_item.setLinkedMap(map_item)
                    title_style = QgsLegendStyle()
                    font = QFont(DefaultFont, legend_title_size)
                    font.setBold(True)
                    title_style.setFont(font)
                    legend_item.setStyle(QgsLegendStyle.Style.Title, title_style)
                    legend_item.setTitle("图例")

                    symbol_label_style = QgsLegendStyle()
                    symbol_label_style.setFont(QFont(DefaultFont, legend_label_size, 1, False))
                    legend_item.setStyle(QgsLegendStyle.Style.SymbolLabel, symbol_label_style)

                    legend_item.rstyle(QgsLegendStyle.Style.Symbol).setMargin(QgsLegendStyle.Side.Top, 0.3)
                    legend_item.rstyle(QgsLegendStyle.Style.Title).setMargin(QgsLegendStyle.Side.Bottom, 1)

                    legend_item.setLegendFilterByMapEnabled(True)
                    legend_item.setAutoUpdateModel(autoUpdate=False)
                    m = legend_item.model()
                    root = m.rootGroup()
                    # group.clear()
                    legend_item.model().setRootGroup(root)

                    for tr in root.children():
                        if tr.layerId() == checked_layer_ids["轨道站点"]:
                            tr.setCustomProperty("legend/title-label", "轨道站点")
                        elif tr.layerId() == checked_layer_ids["POI"]:
                            tr.setCustomProperty("legend/title-label", "POI")
                            QgsLegendRenderer.setNodeLegendStyle(tr, QgsLegendStyle.Style.Hidden)

                    for lr in lyrsToRemove:
                        root.removeLayer(self.project.mapLayer(lr))

                    # root = QgsLayerTree()
                    # for l_name, l_id in checked_layer_ids.items():
                    #     tree_layer = root.addLayer(QgsProject.instance().mapLayer(l_id))
                    #     tree_layer.setUseLayerName(False)
                    #     tree_layer.setName(l_name)
                    #     setattr(root, l_name, QgsLayerTree())

                    # legend_item.updateLegend()
                    legend_item.model().setRootGroup(root)
                    legend_item.setBackgroundColor(QColor(255, 255, 255, 153))
                    # legend_item.updateLegend()
                    legend_item.adjustBoxSize()
                    legend_item.refresh()
                    layout.addLayoutItem(legend_item)

                self.project.write(project_name)

                exporter = QgsLayoutExporter(layout)
                # QgsMessageLog.logMessage(project_name, tag="Plugins", level=Qgis.MessageLevel.Warning)

                if out_format == 'pdf':
                    exporter.exportToPdf(os.path.join(out_path, "pdf", f"out_{fea_id}.pdf"), QgsLayoutExporter.PdfExportSettings())
                else:
                    exporter.exportToImage(os.path.join(out_path, out_format, f"out_{fea_id}.{out_format}"), QgsLayoutExporter.ImageExportSettings())

                self.setProgress(float(ifeat * 100 / total_num))
                ifeat += 1
            return True
        except:
            self.exception = Exception(traceback.format_exc())
            return False

    def finished(self, result: bool) -> None:
        if result:
            QgsMessageLog.logMessage("任务:{}完成, 保存至目录:{}".format(self.description(), self.config.out_path),
                                     tag=MESSAGE_TAG, level=Qgis.MessageLevel.Success)
        else:
            if self.exception is None:
                QgsMessageLog.logMessage("任务:{}失败, 但是未发生错误(可能是人为中止)".format(self.description()),
                                         tag=MESSAGE_TAG, level=Qgis.MessageLevel.Warning)
            else:
                QgsMessageLog.logMessage("任务:{}失败, 错误原因: {}".format(self.description(), self.exception),
                                         tag=MESSAGE_TAG, level=Qgis.MessageLevel.Critical)

    def cancel(self):
        QgsMessageLog.logMessage(
            '任务取消: "{name}"'.format(
                name=self.description()),
            MESSAGE_TAG, Qgis.MessageLevel.Info)
        super().cancel()

    def draw_layout_mapitem(self, layout, out_width, out_height, out_resolution):
        map_item = QgsLayoutItemMap(layout)
        # map_item.setAtlasDriven(True)
        # map_item.setAtlasScalingMode(QgsLayoutItemMap.AtlasScalingMode.Predefined)
        map_item.mapSettings(self.iface.mapCanvas().extent(), QSizeF(out_width, out_height), dpi=out_resolution, includeLayerSettings=True)
        # map.setAtlasMargin(0.05)
        map_item.setRect(0, 0, out_width, out_height)
        map_item.zoomToExtent(self.iface.mapCanvas().extent())
        map_item.setBackgroundColor(QColor(255, 255, 255, 0))
        layout.addLayoutItem(map_item)

        map_item.attemptMove(QgsLayoutPoint(0, 0, QgsUnitTypes.LayoutUnit.LayoutPixels))
        map_item.attemptResize(QgsLayoutSize(out_width, out_height, QgsUnitTypes.LayoutUnit.LayoutPixels))

        return map_item

    def layout_length(self, map_item, length, start_pt):
        layout_start_pt = map_item.mapToItemCoords(QPointF(start_pt.x(), start_pt.y()))
        map_length = self.convert_distance(length)
        layout_end_pt = map_item.mapToItemCoords(QPointF(start_pt.x() + map_length, start_pt.y()))
        return layout_end_pt.x() - layout_start_pt.x()

    def convert_distance(self, distance):
        d = QgsDistanceArea()
        # tr_context = QgsCoordinateTransformContext()
        d.setEllipsoid(self.project.ellipsoid())
        # d.setSourceCrs(source_crs, tr_context)
        # res = d.convertLengthMeasurement(distance, QgsUnitTypes.DistanceUnit.DistanceDegrees)
        res = d.convertLengthMeasurement(distance, self.project.distanceUnits())
        return res

    def get_key_column(self):
        key_list = self.block_layer.primaryKeyAttributes()
        if len(key_list) > 0:
            return key_list[0]
        else:
            return "fid"
