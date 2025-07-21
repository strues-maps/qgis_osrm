# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TemplateOsrm
                                 A QGIS plugin
 Class to be subclassed by each OSRM dialog class
                             -------------------
        begin                : 2015-09-29
        copyright            : (C) 2015 by mthh
        email                : matthieu.viry@cnrs.fr
                              -------------------
        begin                : 2025-07-15
        copyright            : (C) 2025 by strues-maps
        email                : info@strues-maps.lt
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
from urllib.request import urlopen
from functools import lru_cache
import json
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox, QProgressBar
from qgis.core import (  # pylint: disable = no-name-in-module
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsMessageLog, QgsCoordinateTransformContext, Qgis, QgsProject
)
from .osrm_utils import (
    read_providers_config, save_last_provider,
    load_last_provider
)


class TemplateOsrm:
    """
    Template class to be subclassed by each OSRM dialog class.
    It contains some methods used by the five next class.
    """

    def __init__(self):
        self.iface = None
        self.canvas = None
        self.progress = None
        self.origin = None
        self.origin_emit = None
        self.lineEdit_xyO = None  # pylint: disable=invalid-name
        self.combo_box_provider = None
        self.base_url = None
        self.api_key = None
        self.providers = None
        self.last_provider = None

    def load_providers(self):
        """Load providers, mark last used and handle provider change signal"""
        self.load_last_provider()
        self.populate_combo_box_provider()
        self.combo_box_provider.currentTextChanged.connect(
            self.provider_changed
        )

    def display_error(self, error, code):
        """Displays error message in message bar and message log"""
        msg = {
            1: "An error occured when trying to contact the OSRM instance",
            2: "OSRM plugin error report : Too many errors occured "
               "when trying to contact the OSRM instance - "
               "Route calculation has been stopped",
        }
        self.iface.messageBar().clearWidgets()
        self.iface.messageBar().pushMessage(
            "Error",
            msg[code] + "(see QGis log for error traceback)",
            duration=10
        )
        QgsMessageLog.logMessage(
            f"OSRM-plugin error report :\n {error}",
            level=Qgis.Warning
        )

    def make_prog_bar(self):
        """Displays progress bar widget"""
        prog_message_bar = self.iface.messageBar().createMessage(
            "Creation in progress..."
        )
        self.progress = QProgressBar()
        self.progress.setMaximum(100)
        self.progress.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        prog_message_bar.layout().addWidget(self.progress)
        self.iface.messageBar().pushWidget(prog_message_bar, Qgis.Info)

    @staticmethod
    @lru_cache(maxsize=30)
    def query_url(url):
        """Loads and decodes json data from specified url"""
        with urlopen(url) as r:
            return json.loads(r.read(), strict=False)

        return None

    def print_about(self):
        """Shows plugin about dialog box"""
        mbox = QMessageBox(self.iface.mainWindow())
        mbox.setIcon(QMessageBox.Information)
        mbox.setWindowTitle('About')
        mbox.setTextFormat(Qt.RichText)
        mbox.setText(
            "<p><b>(Unofficial) OSRM plugin for QGIS 3.x</b><br><br>"
            "Author: mthh, 2015<br>Author: strues-maps, 2025<br>"
            "Licence : GNU GPL v2<br><br><br>Underlying routing "
            "engine is <a href='http://project-osrm.org'>OSRM</a>"
            "(Open Source Routing Engine) :<br>- Based on <a href='http://"
            "www.openstreetmap.org/copyright'>OpenStreetMap</a> "
            "dataset<br>- Easy to start a local instance<br>"
            "- Pretty fast engine (based on contraction hierarchies and mainly"
            " writen in C++)<br>- Mainly authored by D. Luxen and C. "
            "Vetter<br>(<a href='http://project-osrm.org'>http://project-osrm"
            ".org</a> or <a href='https://github.com/Project-OSRM/osrm"
            "-backend#references-in-publications'>on GitHub</a>)<br></p>")
        mbox.open()

    def store_origin(self, point):
        """
        Method to store a click on the QGIS canvas
        """
        self.origin = self.transform_point_for_storage(self.canvas, point)
        self.canvas.unsetMapTool(self.origin_emit)
        self.lineEdit_xyO.setText(self.transform_point_to_str(self.origin))

    def transform_point_for_storage(self, canvas, point):
        """Convert emited point to point crs used for storage"""
        if '4326' not in canvas.mapSettings().destinationCrs().authid():
            crs_src = canvas.mapSettings().destinationCrs()
            xform = QgsCoordinateTransform(
                crs_src,
                QgsCoordinateReferenceSystem.fromEpsgId(4326),
                QgsCoordinateTransformContext()
            )
            point = xform.transform(point)
        return point

    def transform_point_to_str(self, point):
        """Transform QgsPointXY into string representation"""
        x = round(point.x(), 6)
        y = round(point.y(), 6)

        return f"({x}, {y})"

    def transform_str_to_coords(self, point_str):
        """Transform point string representation into coordinate pair"""
        str_x, str_y = point_str.replace("(", "").replace(")", "").split(", ")
        x = float(str_x)
        y = float(str_y)

        return [x, y]

    def transform_str_to_coords_list(self, points_str):
        """Transform point string representation into coordinate list"""
        point_list = points_str.replace("[", "").replace("]", "").split("), (")
        coord_list = []

        for point_str in point_list:
            coord_list.append(self.transform_str_to_coords(point_str))

        return coord_list

    def prepare_request_url(self, base_url, action):
        """Build request url from base url and appropriate action"""
        return base_url.replace('{action}', action)

    def provider_changed(self):
        """Handle provider selection action"""
        provider_index = self.combo_box_provider.currentIndex()
        provider = self.providers[provider_index]
        self.base_url = provider["base_url"]
        self.api_key = provider["api_key"]
        self.last_provider = provider["name"]
        save_last_provider(provider["name"])

    def load_last_provider(self):
        """Load name of last used provider in plugin"""
        self.last_provider = load_last_provider()

    def populate_combo_box_provider(self):
        """Populates combo box with provider names"""
        try:
            self.providers = read_providers_config()
            names = [
                provider["name"]
                for provider in self.providers
            ]
            self.combo_box_provider.addItems(names)

            if self.last_provider in names:
                provider_index = names.index(self.last_provider)
                self.combo_box_provider.setCurrentIndex(provider_index)
                self.base_url = self.providers[provider_index]["base_url"]
                self.api_key = self.providers[provider_index]["api_key"]
        except (AssertionError, ValueError) as err:
            QMessageBox.warning(
                self.iface.mainWindow(),
                'Error',
                f"Invalid providers configuration file! {err}"
            )
            self.providers = []

    def repaint_layers(self):
        """Repaint layers if at least on of them is visible"""
        layer_tree_root = QgsProject.instance().layerTreeRoot()
        for layer in QgsProject.instance().mapLayers().values():
            layer_tree_layer = layer_tree_root.findLayer(layer)
            if layer_tree_layer.isVisible():
                layer.triggerRepaint()
                return 0

        return 0
