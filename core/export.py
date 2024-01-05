import os.path
import time

from PyQt5.QtCore import QTimer, QSize, QSizeF, QPoint, Qt, QPointF
from PyQt5.QtGui import QPainter, QImage, QColor
from PyQt5.QtWidgets import QMessageBox
from qgis._core import QgsMapSettings, QgsSettings, QgsProject, QgsMessageLog, Qgis, QgsMapLayerType, \
    QgsMapRendererCustomPainterJob, QgsMapRendererParallelJob, QgsMapRendererSequentialJob, QgsPrintLayout, \
    QgsLayoutItemMap, QgsLayoutPoint, QgsUnitTypes, QgsLayoutSize, QgsLayoutExporter, QgsRectangle, QgsLayoutItemPage, \
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsDistanceArea, QgsCoordinateTransformContext, \
    QgsLayoutItemShape, QgsSimpleFillSymbolLayer, QgsFillSymbol, QgsLayoutItem, QgsMapToPixel
from qgis._gui import QgisInterface

from ..utils import get_qset_name, get_field_index_no_case, default_field, ExportDir, epsg_code, PluginConfig


class bacth_export:
    def __init__(self, iface: QgisInterface):
        self.iface = iface
        self.qset = QgsSettings()
        self.project = QgsProject.instance()

    def run(self):
        self.config = PluginConfig(
            key=self.qset.value(get_qset_name("key")),
            random_enabled=True,
            keyisvalid=self.qset.value(get_qset_name("keyisvalid"), type=bool),
            subdomain=self.qset.value(get_qset_name("subdomain")),
            extramap_enabled=True,
            lastpath=self.qset.value(get_qset_name("lastpath")),
            out_width=self.qset.value(get_qset_name("out_width"), type=int),
            out_height=self.qset.value(get_qset_name("out_height"), type=int),
            out_resolution=self.qset.value(get_qset_name("out_resolution"), type=int),
            out_format=self.qset.value(get_qset_name("out_format"), type=str),
            draw_circle=self.qset.value(get_qset_name("draw_circle"), type=bool),
            radius=self.qset.value(get_qset_name("radius"), type=float)
        )

        block_layer_id = self.qset.value(get_qset_name("block_layer_id"))
        if block_layer_id is None:
            return

        block_layer = self.project.mapLayer(block_layer_id)

        if block_layer.type() != QgsMapLayerType.VectorLayer:
            return

        # ms = self.iface.mapCanvas().mapSettings()
        # fni, field_name = get_field_index_no_case(block_layer, default_field.name_block)

        if not os.path.exists(ExportDir):
            os.mkdir(ExportDir)

        out_width = self.config.out_width
        out_height = self.config.out_height
        out_resolution = self.config.out_resolution
        out_format = self.config.out_format
        draw_circle = self.config.draw_circle
        radius = self.config.radius

        if block_layer.crs().isValid():
            if epsg_code(block_layer.crs()) == 4326 or epsg_code(block_layer.crs()) == 4490:
                radius = self.convert_distance(radius)

        QgsMessageLog.logMessage(f"图片格式: {out_width} * {out_height} * {out_resolution}", tag="Plugins", level=Qgis.MessageLevel.Warning)

        layoutName = "renderUP_atlas"
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

        # layout: QgsPrintLayout = manager.layoutByName(layoutName)

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

        p_atlas = layout.atlas()
        p_atlas.setCoverageLayer(block_layer)
        p_atlas.setEnabled(True)

        p_atlas.beginRender()

        circle_symbol_layer = QgsSimpleFillSymbolLayer.create({
            'outline_color': "#C00000",
            'color': '0,0,0,0',
            'outline_width': "5",
            'outline_width_unit': 'Pixel'
        })
        # circle_symbol_layer.setColor(QColor(234, 245, 123, 0))
        circle_symbol = QgsFillSymbol()
        circle_symbol.changeSymbolLayer(0, circle_symbol_layer)
        # circle_symbol.appendSymbolLayer(circle_symbol_layer)

        for i in range(0, p_atlas.count()):
            # Creata a exporter Layout for each layout generate with Atlas
            feature = block_layer.getFeature(i)
            geom = feature.geometry()

            if block_layer.crs().isValid():
                sourceCrs = QgsCoordinateReferenceSystem(epsg_code(block_layer.crs()))
                destCrs = QgsCoordinateReferenceSystem(epsg_code(self.project.crs()))

                if sourceCrs != destCrs:
                    tr = QgsCoordinateTransform(sourceCrs, destCrs, self.project)
                    geom.transform(tr)

            centroid = feature.geometry().pointOnSurface().asPoint()

            extent = QgsRectangle.fromCenterAndSize(centroid, 2 * radius, 2 * radius)
            # extent = geom.boundingBox()
            extent.scale(1.5)
            map_item.zoomToExtent(extent)

            # QgsMessageLog.logMessage(str(extent.asWktPolygon()), tag="Plugins", level=Qgis.MessageLevel.Warning)

            ele_circle = QgsLayoutItemShape(layout)
            ele_circle.setShapeType(QgsLayoutItemShape.Shape.Ellipse)
            ele_circle.setReferencePoint(QgsLayoutItem.ReferencePoint.Middle)
            ele_circle.setSymbol(circle_symbol)
            layout.addLayoutItem(ele_circle)

            QgsMessageLog.logMessage(f"中心点: {centroid.x()}, {centroid.y()}", tag="Plugins", level=Qgis.MessageLevel.Warning)
            # QgsMessageLog.logMessage(f"地图比例尺: {map_item.scale()}", tag="Plugins", level=Qgis.MessageLevel.Warning)
            # QgsMessageLog.logMessage(f"地图单位: {self.project.distanceUnits()}", tag="Plugins", level=Qgis.MessageLevel.Warning)

            # map_convertor = QgsMapToPixel().fromScale(map_item.scale(), self.project.distanceUnits(), self.config.out_resolution)
            # map_convertor = QgsMapToPixel()
            # screen_centroid = map_convertor.transform(centroid)
            layout_centroid = map_item.mapToItemCoords(QPoint(centroid.x(), centroid.y()))
            layout_radius = self.layout_length(map_item, radius, centroid)

            QgsMessageLog.logMessage(f"屏幕中心点: {layout_centroid.x()}, {layout_centroid.y()}", tag="Plugins", level=Qgis.MessageLevel.Warning)
            QgsMessageLog.logMessage(f"屏幕半径: {layout_radius}", tag="Plugins", level=Qgis.MessageLevel.Warning)

            ele_circle.attemptMove(QgsLayoutPoint(layout_centroid.x(), layout_centroid.y(), QgsUnitTypes.LayoutUnit.LayoutMillimeters))
            ele_circle.setFixedSize(QgsLayoutSize(layout_radius, layout_radius))

            exporter = QgsLayoutExporter(p_atlas.layout())
            exporter.exportToImage(os.path.join(ExportDir, p_atlas.currentFilename() + ".jpg"), QgsLayoutExporter.ImageExportSettings())

            # Create Next Layout
            p_atlas.next()

        p_atlas.endRender()

        # map = QgsLayoutItemMap(layout)
        # map.setRect(0, 0, 1000, 1000)
        #
        # # set the map extent
        # ms = QgsMapSettings()
        # ms.setLayers([block_layer])  # set layers to be mapped
        # # ms.setOutputSize(QSize(1000, 1000))
        # rect = QgsRectangle(ms.fullExtent())
        # rect.scale(1.0)
        # ms.setExtent(rect)
        # # map.setExtent(rect)
        # map.zoomToExtent(self.iface.mapCanvas().extent())
        # map.setBackgroundColor(QColor(255, 255, 255, 0))
        # layout.addLayoutItem(map)
        # map.attemptMove(QgsLayoutPoint(0, 0, QgsUnitTypes.LayoutUnit.LayoutPixels))
        # map.attemptResize(QgsLayoutSize(1000, 1000, QgsUnitTypes.LayoutUnit.LayoutPixels))

        # map = QgsLayoutItemMap(layout)
        # map.attemptMove(QgsLayoutPoint(5, 5, QgsUnitTypes.LayoutUnit.LayoutMillimeters))
        # map.attemptResize(QgsLayoutSize(200, 200, QgsUnitTypes.LayoutUnit.LayoutMillimeters))
        # extent = self.iface.mapCanvas().extent()
        # QgsMessageLog.logMessage(str(extent.asWktPolygon()), tag="Plugins", level=Qgis.MessageLevel.Warning)
        # map.zoomToExtent(self.iface.mapCanvas().extent())
        # layout.addItem(map)

        # layout = manager.layoutByName(layoutName)
        # pdf_path = os.path.join(ExportDir, "output.png")
        #
        # exporter = QgsLayoutExporter(layout)
        # out_setting = QgsLayoutExporter.ImageExportSettings()
        # out_setting.imageSize = QSize(1000, 1000)
        # # out_setting.cropToContents = True
        # exporter.exportToImage(pdf_path, out_setting)
        # # exporter.exportToPdf(pdf_path, QgsLayoutExporter.PdfExportSettings())
        QgsMessageLog.logMessage("export ok", tag="Plugins", level=Qgis.MessageLevel.Warning)

        # ms.setOutputSize(QSize(1000, 1000))
        # ms.setFlag(Qgis.MapSettingsFlag.DrawLabeling, False)
        # ms.setFlag(Qgis.MapSettingsFlag.Antialiasing, True)
        # # img = QImage(QSize(1000, 1000), QImage.Format_ARGB32_Premultiplied)
        # for feature in block_layer.getFeatures():
        #     fea_id = str(feature.attributes()[fni])
        #     extent = feature.geometry().boundingBox()
        #     QgsMessageLog.logMessage(str(extent.asWktPolygon()), tag="Plugins", level=Qgis.MessageLevel.Warning)
        #     self.iface.mapCanvas().zoomToFeatureExtent(extent)
        #     self.iface.mapCanvas().setExtent(extent)
        #     self.iface.mapCanvas().refresh()
        #
        #     ms.setExtent(extent)
        #     job = QgsMapRendererParallelJob(ms)
        #     job.start()
        #     job.waitForFinished()
        #     image = job.renderedImage()
        #
        #     # self.iface.mapCanvas().saveAsImage(os.path.join(ExportDir, f"{fea_id}.png"))
        #     image.save(os.path.join(ExportDir, f"{fea_id}.png"))
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
