# -*- coding: utf-8 -*-
"""
/***************************************************************************
 OSRMDialogTSP
                                 A QGIS plugin
 Traveling salesman problem
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

import os
from urllib.error import URLError, HTTPError, ContentTooShortError
from PyQt5 import QtGui, uic
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QDialog
from qgis.core import (  # pylint: disable = no-name-in-module
    QgsMapLayerProxyModel, QgsPoint, QgsProject, QgsVectorLayer,
    QgsSymbol, QgsFeature, QgsGeometry, QgsPalLayerSettings, Qgis,
    QgsSingleSymbolRenderer, QgsMessageLog, QgsTextFormat,
    QgsTextBufferSettings, QgsVectorLayerSimpleLabeling
)
from .osrm_utils import (
    decode_geom, get_coords_ids, prepare_route_symbol, put_on_top
)
from .template_osrm import TemplateOsrm


FORM_CLASS_DIALOG_TSP, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui/osrm_dialog_tsp.ui'))


class OSRMDialogTSP(QDialog, FORM_CLASS_DIALOG_TSP, TemplateOsrm):
    """Dialog for traveling salesman problem"""

    def __init__(self, iface, parent=None):
        """ Constructor"""
        super().__init__(parent)
        TemplateOsrm.__init__(self)
        self.setupUi(self)
        self.iface = iface
        self.pushButton_display.clicked.connect(self.run_tsp)
        self.pushButton_clear.clicked.connect(self.clear_results)
        self.comboBox_layer.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.nb_route = 0
        self.parsed = None
        self.tsp_marker_lr = None
        self.load_providers()

    def clear_results(self):
        """
        Clear previous result and set back counter to 0.
        """
        needs_repaint = False
        for layer in QgsProject.instance().mapLayers():
            if 'tsp_solution_osrm' in layer:
                QgsProject.instance().removeMapLayer(layer)
                needs_repaint = True
            if 'tsp_markers_osrm' in layer:
                QgsProject.instance().removeMapLayer(layer)
                needs_repaint = True
        if needs_repaint:
            self.repaint_layers()
        self.nb_route = 0

    def run_tsp(self):
        """
        Main method, preparing the query and displaying the result on
        the canvas.
        """
        layer = self.comboBox_layer.currentLayer()
        coords, _ = get_coords_ids(
            layer, '', on_selected=self.checkBox_selec_features.isChecked())

        if len(coords) < 2:
            return -1

        query = ''.join(
            [
                self.prepare_request_url(self.base_url, 'trip'),
                ";".join([f"{c[0]},{c[1]}" for c in coords]),
            ]
        )
        if self.api_key:
            query = ''.join([query, '?api_key=', self.api_key])
        print(f"Fetch traveling salesman query: {query}")

        try:
            self.parsed = self.query_url(query)
        except (URLError, HTTPError, ContentTooShortError) as err:
            self.iface.messageBar().pushMessage(
                "Error", "An error occured when trying to contact the OSRM "
                "instance (see QGis log for error traceback)",
                duration=10)
            QgsMessageLog.logMessage(
                f"OSRM-plugin error report :\n {err}",
                level=Qgis.Warning)
            return -1

        try:
            line_geoms = \
                [decode_geom(self.parsed['trips'][i]['geometry'])
                 for i in range(len(self.parsed['trips']))]
        except KeyError:
            self.iface.messageBar().pushMessage(
                "Error",
                "?...",
                duration=5)
            return -1

        tsp_route_layer = QgsVectorLayer(
            "Linestring?crs=epsg:4326&field=id:integer"
            "&field=total_time:integer(20)&field=distance:integer(20)",
            f"tsp_solution_osrm{self.nb_route}", "memory")
        my_symb = prepare_route_symbol(self.nb_route)
        tsp_route_layer.setRenderer(QgsSingleSymbolRenderer(my_symb))
        features = []
        for trip_idx, feature in enumerate(self.parsed['trips']):
            ft = QgsFeature()
            ft.setGeometry(line_geoms[trip_idx])
            ft.setAttributes([trip_idx,
                              feature['distance'],
                              feature['duration']])
            features.append(ft)
            self.prepare_ordered_marker(coords)
        tsp_route_layer.dataProvider().addFeatures(features)
        tsp_route_layer.updateExtents()
        QgsProject.instance().addMapLayer(tsp_route_layer)
        self.iface.setActiveLayer(tsp_route_layer)
        self.iface.zoomToActiveLayer()
        put_on_top(self.tsp_marker_lr.id(), tsp_route_layer.id())
        self.nb_route += 1
#        if self.checkBox_instructions.isChecked():
#            pr_instruct, instruct_layer = self.prep_instruction()
#            QgsProject.instance().addMapLayer(instruct_layer)
#            self.iface.setActiveLayer(instruct_layer)
        return 0

    def prepare_ordered_marker(self, coords):
        """
        Try to display nice marker on a point layer, showing the order of
        the path computed by OSRM.
        """
        self.tsp_marker_lr = QgsVectorLayer(
            "Point?crs=epsg:4326&field=id:integer"
            "&field=TSP_nb:integer(20)&field=Origin_nb:integer(20)",
            f"tsp_markers_osrm{self.nb_route}", "memory")
        symbol = QgsSymbol.defaultSymbol(self.tsp_marker_lr.geometryType())
        symbol.setSize(4.5)
        symbol.setColor(QtGui.QColor("yellow"))

        features = []
        waypoint_nb = len(self.parsed['waypoints'])

        for i in range(0, waypoint_nb):
            waypoint = self.parsed['waypoints'][i]
            trip_idx = waypoint['waypoint_index']
            pt = coords[i]

            ft = QgsFeature()
            ft.setGeometry(QgsGeometry.fromPoint(QgsPoint(pt)))
            ft.setAttributes([trip_idx, trip_idx + 1, i])
            features.append(ft)

        self.tsp_marker_lr.dataProvider().addFeatures(features)

        settings = QgsPalLayerSettings()
        settings.placement = Qgis.LabelPlacement.OverPoint
        text_format = QgsTextFormat()
        text_format.setFont(QFont('Arial', 12))
        text_format.setColor(QColor('Black'))
        buffer = QgsTextBufferSettings()
        buffer.setEnabled(True)
        buffer.setSize(0.50)
        buffer.setColor(QColor('grey'))
        text_format.setBuffer(buffer)
        settings.setFormat(text_format)
        settings.fieldName = 'TSP_nb'
        settings.isExpression = True
        labels = QgsVectorLayerSimpleLabeling(settings)

        self.tsp_marker_lr.setLabelsEnabled(True)
        self.tsp_marker_lr.setLabeling(labels)
        self.tsp_marker_lr.setRenderer(QgsSingleSymbolRenderer(symbol))

        QgsProject.instance().addMapLayer(self.tsp_marker_lr)
