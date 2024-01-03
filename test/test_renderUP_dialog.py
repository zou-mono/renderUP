# coding=utf-8
"""Dialog test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'zou_mono@sina.com'
__date__ = '2023-12-28'
__copyright__ = 'Copyright 2023, mono zou'

import os
import unittest

from PyQt5.QtGui import QColor
from qgis.PyQt.QtWidgets import QDialogButtonBox, QDialog
from qgis._core import QgsProject, QgsSimpleLineSymbolLayer, QgsVectorLayer, QgsSymbolLayer, QgsProperty

from ui.render_dlg import renderDialog, categrorized_renderer

from utilities import get_qgis_app
from utils import get_field_index_no_case, default_field, metro_line_color_dict

QGIS_APP = get_qgis_app()

TEST_DATA_DIR = '../data'

class renderUPDialogTest(unittest.TestCase):
    """Test dialog works."""

    def setUp(self):
        """Runs before each test."""
        self.project = QgsProject.instance()
        self.dialog = renderDialog(project=self.project)

    def tearDown(self):
        """Runs after each test."""
        self.dialog = None

    def test_render_metro_network(self):
        lines_shp = os.path.join(TEST_DATA_DIR, '2035年地铁线路_WGS84_2023-12-28_19-14-32_CGCS2000投影_2023-12-28_21-05-15.shp')
        lines_layer = QgsVectorLayer(lines_shp, 'Lines', 'ogr')
        QgsProject.instance().addMapLayer(lines_layer)

        layer = QgsSimpleLineSymbolLayer()
        # layer.setDataDefinedProperty(QgsSymbolLayer.PropertyLayerEnabled, QgsProperty.fromExpression("Name='Highway'"))
        layer.setColor(QColor(100, 150, 150))
        layer.setWidth(5)

        fni, field_name = get_field_index_no_case(lines_layer, default_field.name_metro_line_id)

        network_type = {}
        spec_dict = {}
        for fea in lines_layer.getFeatures():
            lineid = str(fea.attributes()[fni])
            network_type[lineid] = f"{lineid}号线"
            symbol_layer = QgsSimpleLineSymbolLayer.create({
                'color': metro_line_color_dict[lineid],
                # 'outline_color': metro_line_color_dict[lineid],
            })

            spec_dict[lineid] = symbol_layer

        categrorized_renderer(layer, fni, network_type, field_name, spec_dict=spec_dict)

    def test_dialog_ok(self):
        """Test we can click OK."""

        button = self.dialog.button_box.button(QDialogButtonBox.Ok)
        button.click()
        result = self.dialog.result()
        self.assertEqual(result, QDialog.Accepted)

    def test_dialog_cancel(self):
        """Test we can click cancel."""
        button = self.dialog.button_box.button(QDialogButtonBox.Cancel)
        button.click()
        result = self.dialog.result()
        self.assertEqual(result, QDialog.Rejected)


if __name__ == "__main__":
    suite = unittest.makeSuite(renderUPDialogTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)

