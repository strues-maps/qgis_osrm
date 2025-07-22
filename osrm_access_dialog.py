# -*- coding: utf-8 -*-
"""
/***************************************************************************
 OSRMAccessDialog
                                 A QGIS plugin
 Calculating access isochrones
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
from re import match
from multiprocessing.pool import ThreadPool
import numpy as np
from PyQt5 import QtGui, uic
from PyQt5.QtWidgets import QMessageBox, QDialog
from qgis.gui import QgsMapToolEmitPoint  # pylint: disable = no-name-in-module
from qgis.core import (  # pylint: disable = no-name-in-module
    QgsMapLayerProxyModel, QgsFeature, QgsProject, QgsPointXY,
    QgsGeometry, QgsSymbol, QgsGraduatedSymbolRenderer,
    QgsVectorLayer, QgsRendererRange, QgsFillSymbol,
    QgsSingleSymbolRenderer
)
from .osrm_utils import get_isochrones_colors, prep_access, get_coords_ids
from .osrm_polyfill import Qgis_GeometryType_Point
from .template_osrm import TemplateOsrm


FORM_CLASS_ACCESS_DIALOG_BASE, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui/osrm_access_dialog_base.ui'))


class OSRMAccessDialog(QDialog, FORM_CLASS_ACCESS_DIALOG_BASE, TemplateOsrm):
    """Dialog for calculating access isochrones"""
    def __init__(self, iface, parent=None):
        """Constructor."""
        super().__init__(parent)
        TemplateOsrm.__init__(self)

        self.setupUi(self)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.origin_emit = QgsMapToolEmitPoint(self.canvas)
        self.intermediate_emit = QgsMapToolEmitPoint(self.canvas)
        self.comboBox_pointlayer.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.comboBox_method.activated[str].connect(self.enable_functionnality)
        self.pushButton_fetch.clicked.connect(self.get_access_isochrones)
        self.pushButtonClear.clicked.connect(self.clear_all_isochrone)
        self.close_button_box.clicked.connect(self.close_button_clicked)
        self.lineEdit_xyO.textChanged.connect(self.change_nb_center)
        self.intermediate = []
        self.nb_isocr = 0
        self.progress = None
        self.polygons = None
        self.max_points = 0
        self.load_providers()

    def closeEvent(self, event):  # pylint: disable=invalid-name
        """Handle window close event"""
        self.canvas.unsetMapTool(self.origin_emit)
        self.canvas.unsetMapTool(self.intermediate_emit)
        super().closeEvent(event)

    def close_button_clicked(self):
        """Handle close button in dialog event"""
        self.canvas.unsetMapTool(self.origin_emit)
        self.canvas.unsetMapTool(self.intermediate_emit)

    def change_nb_center(self):
        """Update isochrones centers count in UI"""
        # nb_center = self.lineEdit_xyO.text().count('(')

    def enable_functionnality(self, text):
        """Load preset functionality groups according to text parameter"""
        functions = (
            self.pushButtonIntermediate.setEnabled,
            self.lineEdit_xyO.setEnabled,
            self.comboBox_pointlayer.setEnabled,
            self.label_3.setEnabled,
            self.checkBox_selectedFt.setEnabled,
            self.pushButton_fetch.setEnabled
        )
        if 'clicking' in text:
            values = (True, True, False, False, False, True)
        elif 'selecting' in text:
            values = (False, False, True, True, True, True)
        elif 'method' in text:
            values = (False, False, False, False, False, False)
        else:
            return
        for func, bool_value in zip(functions, values):
            func(bool_value)

    def clear_all_isochrone(self):
        """
        Clear previously done isochrone polygons and clear the coordinate field
        """
        self.lineEdit_xyO.setText('')
        self.intermediate = []
        self.nb_isocr = 0
        needs_repaint = False
        for layer in QgsProject.instance().mapLayers():
            if 'isochrone_osrm' in layer or 'isochrone_center' in layer:
                QgsProject.instance().removeMapLayer(layer)
                needs_repaint = True
        if needs_repaint:
            self.repaint_layers()

    def store_intermediate_acces(self, point):
        """Store intermediate isochrone point"""
        point = self.transform_point_for_storage(self.canvas, point)
        self.intermediate.append(tuple(map(lambda x: round(x, 6), point)))
        self.canvas.unsetMapTool(self.intermediate_emit)
        self.lineEdit_xyO.setText(str(self.intermediate))

    def get_points_from_canvas(self):
        """
        Retrieve intermediary isochrone point coordinates from Qt line editor
        """
        pts = self.lineEdit_xyO.text()
        try:
            assert match('^[^a-zA-Z]+$', pts) and len(pts) > 4
            return self.transform_str_to_coords_list(pts)
        except (AssertionError, ValueError):
            QMessageBox.warning(
                self.iface.mainWindow(),
                'Error',
                "Invalid coordinates selected!"
            )
            return None

    def add_final_pts(self, pts):
        """Add intermediary isochrone points to layer"""
        center_pt_layer = QgsVectorLayer(
            "Point?crs=epsg:4326&field=id_center:integer&"
            "field=role:string(80)",
            f"isochrone_center_{self.nb_isocr}",
            "memory"
        )
        my_symb = QgsSymbol.defaultSymbol(Qgis_GeometryType_Point())
        my_symb.setColor(QtGui.QColor("#e31a1c"))
        my_symb.setSize(1.2)
        center_pt_layer.setRenderer(QgsSingleSymbolRenderer(my_symb))
        features = []
        for nb, pt in enumerate(pts):
            xo, yo = pt["point"]
            fet = QgsFeature()
            fet.setGeometry(QgsGeometry.fromPointXY(
                QgsPointXY(float(xo), float(yo))))
            fet.setAttributes([nb, 'Origin'])
            features.append(fet)
        center_pt_layer.dataProvider().addFeatures(features)
        QgsProject.instance().addMapLayer(center_pt_layer)

    def get_access_isochrones(self):
        """
        Making the accessibility isochrones in few steps:
        - make a grid of points aroung the origin point,
        - snap each point (using OSRM locate function) on the road network,
        - get the time-distance between the origin point and each of these pts
            (using OSRM table function),
        - make an interpolation grid to extract polygons corresponding to the
            desired time intervals (using scipy library),
        - render the polygon.
        """
        if 'clicking' in self.comboBox_method.currentText():
            pts = self.intermediate
        elif 'selecting' in self.comboBox_method.currentText():
            layer = self.comboBox_pointlayer.currentLayer()
            pts, _ = get_coords_ids(
                layer,
                '',
                on_selected=self.checkBox_selectedFt.isChecked()
            )
            pts = tuple(pts)

        if not pts:
            return

        max_time = self.spinBox_max.value()
        interval_time = self.spinBox_intervall.value()
        nb_inter = int(round(max_time / interval_time)) + 1
        levels = tuple(
            list(
                range(0, int(max_time + 1) + interval_time, interval_time)
            )[:nb_inter]
        )

        self.make_prog_bar()
        self.max_points = 1500 if len(pts) == 1 else 500
        self.polygons = []

        pts = [
            {
                "point": pt,
                "max": max_time,
                "levels": levels,
                "url": self.prepare_request_url(self.base_url, 'table'),
                "max_points": self.max_points,
                "api_key": self.api_key
            }
            for pt in pts
        ]

        pool = ThreadPool(processes=4 if len(pts) >= 4 else len(pts))
        self.progress.setValue(5)

        try:
            self.polygons = list(pool.map(prep_access, pts))
            pool.close()
        except ValueError as err:
            self.display_error(err, 1)
            pool.close()
            return

        if len(self.polygons) == 1:
            self.polygons = self.polygons[0]
        else:
            self.polygons = np.array(self.polygons).transpose().tolist()
            self.polygons = \
                [QgsGeometry.unaryUnion(polys) for polys in self.polygons]

        isochrone_layer = QgsVectorLayer(
            "MultiPolygon?crs=epsg:4326&field=id:integer"
            "&field=min:integer(10)"
            "&field=max:integer(10)",
            f"isochrone_osrm_{self.nb_isocr}", "memory")
        data_provider = isochrone_layer.dataProvider()

        # Add the features to the layer to display :
        features = []
        levels = levels[1:]
        self.progress.setValue(85)
        for i, poly in enumerate(self.polygons):
            if not poly:
                continue
            ft = QgsFeature()
            ft.setGeometry(poly)
            ft.setAttributes(
                [i, levels[i] - interval_time, levels[i]])
            features.append(ft)
        data_provider.addFeatures(features[::-1])
        self.nb_isocr += 1
        self.progress.setValue(95)

        # Render the value :
        renderer = self.prepare_renderer(
            levels, interval_time, len(self.polygons))
        isochrone_layer.setRenderer(renderer)
        isochrone_layer.setOpacity(0.25)
        self.iface.messageBar().clearWidgets()
        QgsProject.instance().addMapLayer(isochrone_layer)

        self.add_final_pts(pts)
        self.iface.setActiveLayer(isochrone_layer)

    @staticmethod
    def prepare_renderer(levels, inter_time, lenpoly):
        """Build renderer for isochrones"""
        cats = [
            (f"{levels[i] - inter_time} - {levels[i]} min",
             levels[i] - inter_time,
             levels[i])
            for i in range(lenpoly)
        ]  # label, lower bound, upper bound
        colors = get_isochrones_colors(len(levels))
        ranges = []
        for ix, cat in enumerate(cats):
            symbol = QgsFillSymbol()
            symbol.setColor(QtGui.QColor(colors[ix]))
            rng = QgsRendererRange(cat[1], cat[2], symbol, cat[0])
            ranges.append(rng)
        expression = 'max'
        return QgsGraduatedSymbolRenderer(expression, ranges)
