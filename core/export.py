import os.path
import random
import time

from PyQt5.QtCore import QTimer, QSize, QSizeF, QPoint, Qt, QPointF, QThread, pyqtSignal
from PyQt5.QtGui import QPainter, QImage, QColor
from PyQt5.QtWidgets import QMessageBox
from qgis._core import QgsMapSettings, QgsSettings, QgsProject, QgsMessageLog, Qgis, QgsMapLayerType, \
    QgsMapRendererCustomPainterJob, QgsMapRendererParallelJob, QgsMapRendererSequentialJob, QgsPrintLayout, \
    QgsLayoutItemMap, QgsLayoutPoint, QgsUnitTypes, QgsLayoutSize, QgsLayoutExporter, QgsRectangle, QgsLayoutItemPage, \
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsDistanceArea, QgsCoordinateTransformContext, \
    QgsLayoutItemShape, QgsSimpleFillSymbolLayer, QgsFillSymbol, QgsLayoutItem, QgsMapToPixel, QgsTask
from qgis._gui import QgisInterface

from ..utils import get_qset_name, get_field_index_no_case, default_field, ExportDir, epsg_code, PluginConfig, \
    MESSAGE_TAG

MESSAGE_CATEGORY = 'RenderUP'

#
class bacth_export(QgsTask):
    def __init__(self, description, iface, block_layer):
        super(bacth_export, self).__init__(description)
        self.qset = QgsSettings()
        self.block_layer = block_layer
        self.iface = iface
        self.project = QgsProject.instance()

    def run(self):
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
            draw_circle=self.qset.value(get_qset_name("draw_circle"), type=bool),
            radius=self.qset.value(get_qset_name("radius"), type=float)
        )

        out_width = self.config.out_width
        out_height = self.config.out_height
        out_resolution = self.config.out_resolution
        out_format = self.config.out_format
        draw_circle = self.config.draw_circle
        radius = self.config.radius
        out_path = os.path.join(self.config.out_path)
        #
        # if block_layer.crs().isValid():
        #     if epsg_code(block_layer.crs()) == 4326 or epsg_code(block_layer.crs()) == 4490:
        #         radius = self.convert_distance(radius)
        #
        # QgsMessageLog.logMessage(f"图片格式: {out_width} * {out_height} * {out_resolution}", tag=MESSAGE_TAG, level=Qgis.MessageLevel.Warning)

        layoutName = "renderUP_layout"
        manager = self.project.layoutManager()
        layouts_list = manager.printLayouts()
        # remove any duplicate layouts
        for layout in layouts_list:
            if layout.name() == layoutName:
                manager.removeLayout(layout)
        layout = QgsPrintLayout(QgsProject.instance())
        layout.initializeDefaults()
        layout.setName(layoutName)
        self.project.layoutManager().addLayout(layout)
        pc = layout.pageCollection()
        pc.pages()[0].setPageSize(QgsLayoutSize(out_width, out_height, QgsUnitTypes.LayoutUnit.LayoutPixels))

        map_item = self.draw_layout_mapitem(layout, out_width, out_height, out_resolution)

        circle_symbol_layer = QgsSimpleFillSymbolLayer.create({
            'outline_color': "64,64,64,77",
            'color': '0,0,0,0',
            'outline_style': 'dot',
            'outline_width': "5",
            'outline_width_unit': 'Pixel'
        })
        circle_symbol = QgsFillSymbol()
        circle_symbol.changeSymbolLayer(0, circle_symbol_layer)

        i = 1
        total_num = self.block_layer.featureCount()
        for feature in  self.block_layer.getFeatures():
            fea_id = str(feature.id())
            geom = feature.geometry()
            project_name = os.path.join(out_path, "project_files", f"{fea_id}.qgs")

            if self.block_layer.crs().isValid():
                sourceCrs = QgsCoordinateReferenceSystem(epsg_code(self.block_layer.crs()))
                destCrs = QgsCoordinateReferenceSystem(epsg_code(self.project.crs()))

                if sourceCrs != destCrs:
                    tr = QgsCoordinateTransform(sourceCrs, destCrs, self.project)
                    geom.transform(tr)

            centroid = feature.geometry().pointOnSurface().asPoint()
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
                layout.addLayoutItem(ele_circle)

                layout_centroid = map_item.mapToItemCoords(QPoint(centroid.x(), centroid.y()))
                layout_radius = self.layout_length(map_item, radius, centroid)

                ele_circle.attemptMove(QgsLayoutPoint(layout_centroid.x(), layout_centroid.y(), QgsUnitTypes.LayoutUnit.LayoutMillimeters))
                ele_circle.setFixedSize(QgsLayoutSize(2 * layout_radius, 2 * layout_radius))

            exporter = QgsLayoutExporter(layout)

            self.project.write(project_name)
            # QgsMessageLog.logMessage(project_name, tag="Plugins", level=Qgis.MessageLevel.Warning)

            if out_format == 'pdf':
                exporter.exportToPdf(os.path.join(out_path, "pdf", f"out_{fea_id}.pdf"), QgsLayoutExporter.PdfExportSettings())
            else:
                exporter.exportToImage(os.path.join(out_path, out_format, f"out_{fea_id}.{out_format}"), QgsLayoutExporter.ImageExportSettings())

            self.setProgress(float(i * 100 / total_num))
            i += 1
        return True

    def finished(self, result: bool) -> None:
        QgsMessageLog.logMessage("export ok", tag=MESSAGE_TAG, level=Qgis.MessageLevel.Warning)

    def draw_layout_mapitem(self, layout, out_width, out_height, out_resolution):
        map_item = QgsLayoutItemMap(layout)
        map_item.setAtlasDriven(True)
        map_item.setAtlasScalingMode(QgsLayoutItemMap.AtlasScalingMode.Predefined)
        map_item.mapSettings(self.iface.mapCanvas().extent(), QSizeF(out_width, out_height), dpi=out_resolution, includeLayerSettings=True)
        # map.setAtlasMargin(0.05)
        map_item.setRect(0, 0, out_width, out_height)
        # map.zoomToExtent(self.iface.mapCanvas().extent())
        map_item.setBackgroundColor(QColor(255, 255, 255, 0))
        layout.addLayoutItem(map_item)

        map_item.attemptMove(QgsLayoutPoint(0, 0, QgsUnitTypes.LayoutUnit.LayoutPixels))
        map_item.attemptResize(QgsLayoutSize(out_width, out_height, QgsUnitTypes.LayoutUnit.LayoutPixels))

        return map_item

    def layout_length(self, map_item, length, start_pt):
        layout_start_pt = map_item.mapToItemCoords(QPoint(start_pt.x(), start_pt.y()))
        map_length = self.convert_distance(length)
        layout_end_pt = map_item.mapToItemCoords(QPoint(start_pt.x() + map_length, start_pt.y()))
        return layout_end_pt.x() - layout_start_pt.x()

    def convert_distance(self, distance):
        d = QgsDistanceArea()
        # tr_context = QgsCoordinateTransformContext()
        d.setEllipsoid(self.project.ellipsoid())
        # d.setSourceCrs(source_crs, tr_context)
        # res = d.convertLengthMeasurement(distance, QgsUnitTypes.DistanceUnit.DistanceDegrees)
        res = d.convertLengthMeasurement(distance, self.project.distanceUnits())
        return res

