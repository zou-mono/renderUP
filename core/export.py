import os.path
import time

from PyQt5.QtCore import QTimer, QSize
from PyQt5.QtGui import QPainter, QImage, QColor
from PyQt5.QtWidgets import QMessageBox
from qgis._core import QgsMapSettings, QgsSettings, QgsProject, QgsMessageLog, Qgis, QgsMapLayerType, \
    QgsMapRendererCustomPainterJob, QgsMapRendererParallelJob, QgsMapRendererSequentialJob, QgsPrintLayout, \
    QgsLayoutItemMap, QgsLayoutPoint, QgsUnitTypes, QgsLayoutSize, QgsLayoutExporter, QgsRectangle, QgsLayoutItemPage
from qgis._gui import QgisInterface

from ..utils import get_qset_name, get_field_index_no_case, default_field, ExportDir


class bacth_export:
    def __init__(self, iface: QgisInterface):
        self.iface = iface
        self.qset = QgsSettings()
        self.project = QgsProject.instance()

    def run(self):
        block_layer_id = self.qset.value(get_qset_name("block_layer_id"))
        if block_layer_id is None:
            return

        block_layer = self.project.mapLayer(block_layer_id)

        if block_layer.type() != QgsMapLayerType.VectorLayer:
            return

        # QMessageBox.warning(None, '警告', '为了配合影像底图使用，请将当前坐标系统调整为web墨卡托投影(EPSG:3857)或者国家大地2000投影(EPSG:4547)',
        #                     QMessageBox.Ok)

        ms = self.iface.mapCanvas().mapSettings()

        fni, field_name = get_field_index_no_case(block_layer, default_field.name_block)

        if not os.path.exists(ExportDir):
            os.mkdir(ExportDir)

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
        pc.pages()[0].setPageSize(QgsLayoutSize(2000, 2000, QgsUnitTypes.LayoutUnit.LayoutPixels))

        # layout: QgsPrintLayout = manager.layoutByName(layoutName)

        map = QgsLayoutItemMap(layout)
        map.setAtlasDriven(True)
        map.setAtlasScalingMode(QgsLayoutItemMap.AtlasScalingMode.Predefined)
        # map.setAtlasMargin(0.05)
        map.setRect(0, 0, 2000, 2000)
        map.zoomToExtent(self.iface.mapCanvas().extent())
        map.setBackgroundColor(QColor(255, 255, 255, 0))
        layout.addLayoutItem(map)

        map.attemptMove(QgsLayoutPoint(0, 0, QgsUnitTypes.LayoutUnit.LayoutPixels))
        map.attemptResize(QgsLayoutSize(2000, 2000, QgsUnitTypes.LayoutUnit.LayoutPixels))

        p_atlas = layout.atlas()
        p_atlas.setCoverageLayer(block_layer)
        p_atlas.setEnabled(True)

        p_atlas.beginRender()

        for i in range(0, p_atlas.count()):
            # Creata a exporter Layout for each layout generate with Atlas
            feature = block_layer.getFeature(i)
            extent = feature.geometry().boundingBox()
            extent.scale(1.5)

            centroid = feature.geometry().pointOnSurface()



            map.zoomToExtent(extent)
            exporter = QgsLayoutExporter(p_atlas.layout())

            QgsMessageLog.logMessage(f"保存文件: {i} of {p_atlas.count()}", tag="Plugins", level=Qgis.MessageLevel.Warning)

            # # If you want create a PDF's Files
            # exporter.exportToPdf('c:/temp/'+myAtlas.currentFilename()+".pdf", QgsLayoutExporter.PdfExportSettings())

            # If you want create a JPG's files
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