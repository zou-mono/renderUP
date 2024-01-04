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

from PyQt5.QtCore import QThread, pyqtSignal, QSize, QRegularExpression
from PyQt5.QtGui import QIntValidator, QRegularExpressionValidator
from PyQt5.QtWidgets import QFileDialog
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis._core import QgsMessageLog, Qgis, QgsProject, QgsMapLayerType, QgsWkbTypes, QgsSettings

from ..utils import PluginConfig, get_qset_name, tianditu_map_url, check_subdomains, check_key_format, PLUGIN_NAME, \
    check_url_status

log = logging.getLogger('QGIS')

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'setting_style.ui'))


class SettingDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, project, extra_map_action, parent=None):
        """Constructor."""
        super(SettingDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.setFixedSize(QSize(480, 300))

        self.project: QgsProject = project

        self.ping_thread = None
        self.check_thread = None
        self.extra_map_action = extra_map_action

        # 读取配置
        self.qset = QgsSettings()
        self.config = PluginConfig(
            key=self.qset.value(get_qset_name("key")),
            random_enabled=True,
            keyisvalid=self.qset.value(get_qset_name("keyisvalid"), type=bool),
            subdomain=self.qset.value(get_qset_name("subdomain")),
            extramap_enabled=True,
            lastpath=self.qset.value(get_qset_name("lastpath")),
            out_width=self.qset.value(get_qset_name("out_width")),
            out_height=self.qset.value(get_qset_name("out_height")),
            out_resolution=self.qset.value(get_qset_name("out_resolution")),
            out_format=self.qset.value(get_qset_name("out_format"))
        )

        self.mLineEdit_key.setText(self.config.key)
        if len(self.mLineEdit_key.text()) == 0:
            self.pushButton.setEnabled(False)
        self.mLineEdit_key.textChanged.connect(self.on_key_LineEdit_changed)
        if self.config.keyisvalid:
            self.label_keystatus.setText("正常")
        else:
            self.label_keystatus.setText("无效")

        reg = QRegularExpression(r"^[1-9][0-9]*$")
        int_validator = QRegularExpressionValidator()
        int_validator.setRegularExpression(reg)
        self.txt_width.setValidator(int_validator)
        self.txt_height.setValidator(int_validator)
        self.txt_resolution.setValidator(int_validator)

        self.txt_width.setText(str(self.config.out_width))
        self.txt_height.setText(str(self.config.out_height))
        self.txt_resolution.setText(str(self.config.out_resolution))

        self.cmb_format.addItems(['png', 'jpg', 'pdf', 'bmp', 'tif', 'pdf'])
        self.cmb_format.setCurrentText('png')

        self.pushButton.clicked.connect(self.check)

        self.ping_thread = PingUrlThread(self.config.key)
        # self.ping_thread.ping_finished.connect(self.handle_ping_finished)
        self.ping_thread.start()

        self.btn_select_file.clicked.connect(self.btn_selectfile_clicked)

    def closeEvent(self, event):
        self.qset.setValue(f"{PLUGIN_NAME}/extra/out_width", int(self.txt_width.text()))
        self.qset.setValue(f"{PLUGIN_NAME}/extra/out_height", int(self.txt_height.text()))
        self.qset.setValue(f"{PLUGIN_NAME}/extra/out_resolution", int(self.txt_resolution.text()))
        self.qset.setValue(f"{PLUGIN_NAME}/extra/out_format", self.cmb_format.currentText())

        super(SettingDialog, self).close()

    #  选择输出目录
    def btn_selectfile_clicked(self):
        last_path = self.qset.value(get_qset_name("lastpath"))

        fileName = QtWidgets.QFileDialog.getExistingDirectory(self, "选择输出结果的文件夹",
                                                              last_path, QFileDialog.ShowDirsOnly)

        self.mlineEdit_outpath.setText(fileName)
        self.qset.setValue(get_qset_name("lastpath"), last_path)

    def handle_ping_finished(self, status):
        min_time = min(status)
        min_index = status.index(min_time)
        # for i in range(8):
        #     self.comboBox.setItemText(i, f"t{i} {status[i]}")
        # self.comboBox.setItemText(min_index, f"t{min_index} {status[min_index]}*")

    def on_key_LineEdit_changed(self):
        self.pushButton.setEnabled(True)
        current_text = self.mLineEdit_key.text()
        # 删除key中的空格以及非打印字符
        filtered_text = "".join(
            [c for c in current_text if c.isprintable() and not c.isspace()]
        )
        if filtered_text != current_text:
            self.mLineEdit_key.setText(filtered_text)
        # 检查key格式
        key_format = check_key_format(current_text)
        if key_format["key_length_error"]:
            self.label_keystatus.setText("无效key: 格式错误(长度不对)")
            self.pushButton.setEnabled(False)
        elif key_format["has_special_character"]:
            self.label_keystatus.setText("无效key: 含非常规字符")
            self.pushButton.setEnabled(False)
        else:
            self.label_keystatus.setText("未知")
            self.pushButton.setEnabled(True)

    def check(self):
        """检查key是否有效"""
        self.qset.setValue(f"{PLUGIN_NAME}/tianditu/key",  self.mLineEdit_key.text())
        self.label_keystatus.setText("检查中...")
        self.check_thread = CheckThread(self.qset)
        self.check_thread.key = self.mLineEdit_key.text()
        self.check_thread.check_finished.connect(self.label_keystatus.setText)
        self.check_thread.start()


class CheckThread(QThread):
    check_finished = pyqtSignal(str)

    def __init__(self, qset):
        super().__init__()
        self.qset = qset
        self.key = ""

    def run(self):
        url = tianditu_map_url("vec", self.key, "t0")
        tile_url = url.format(x=0, y=0, z=0)
        check_msg = check_url_status(tile_url)
        if check_msg["code"] == 0:
            self.check_finished.emit("正常")
            self.qset.setValue(f"{PLUGIN_NAME}/tianditu/keyisvalid", True)
        else:
            error_msg = f"{check_msg['msg']}: {check_msg['resolve']}"
            self.check_finished.emit(error_msg)
            self.qset.setValue(f"{PLUGIN_NAME}/tianditu/keyisvalid", False)


class PingUrlThread(QThread):
    ping_finished = pyqtSignal(list)

    def __init__(self, key):
        super().__init__()
        self.key = key

    def run(self):
        subdomain_list = ["t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7"]
        urls = [
            tianditu_map_url("vec", self.key, subdomain) for subdomain in subdomain_list
        ]
        status = check_subdomains(urls)
        self.ping_finished.emit(status)