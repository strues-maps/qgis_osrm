# -*- coding: utf-8 -*-
"""
/***************************************************************************
 OSRMBatchRouteDialog
                                 A QGIS plugin
 Batch route calculation
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
from multiprocessing.pool import ThreadPool
from PyQt5 import uic
from PyQt5.QtWidgets import QMessageBox, QDialog
from qgis.core import (  # pylint: disable = no-name-in-module
    QgsMapLayerProxyModel, QgsMessageLog,
    QgsCoordinateTransform, QgsFeature, QgsCoordinateReferenceSystem,
    QgsProject, QgsVectorLayer, QgsVectorFileWriter,
    QgsCoordinateTransformContext, Qgis
)
from .osrm_utils import decode_geom, save_dialog_geo, open_dialog, read_csv
from .template_osrm import TemplateOsrm


FORM_CLASS_BATCH_ROUTE, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui/osrm_batch_route.ui'))

FORM_CLASS_DIALOG_TSP, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui/osrm_dialog_tsp.ui'))


class OSRMBatchRouteDialog(QDialog, FORM_CLASS_BATCH_ROUTE, TemplateOsrm):
    """Batch route calculation dialog"""

    def __init__(self, iface, parent=None):
        """Constructor."""
        super().__init__(parent)
        TemplateOsrm.__init__(self)

        self.setupUi(self)
        self.iface = iface
        self.ComboBoxOrigin.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.ComboBoxDestination.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.pushButtonReverse.clicked.connect(
            self.reverse_origin_destination_batch)
        self.pushButtonBrowse.clicked.connect(self.output_dialog_geo)
        self.pushButtonCsv.clicked.connect(self.input_dialog_csv)
        self.pushButtonRun.clicked.connect(self.get_batch_route)
        self.pushButtonClear.clicked.connect(self.clear_all_routes)
        self.comboBox_method.activated[str].connect(self.enable_functionnality)
        self.nb_route = 0
        self.nb_done = 0
        self.errors = 0
        self.filename = None
        self.encoding = None
        self.csv_data = None
        self.load_providers()

    def clear_all_routes(self):
        """
        Clear previously done route paths
        """
        self.nb_route = 0
        self.nb_done = 0
        needs_repaint = False
        for layer in QgsProject.instance().mapLayers():
            if 'routes_osrm' in layer:
                QgsProject.instance().removeMapLayer(layer)
                needs_repaint = True
        if needs_repaint:
            self.repaint_layers()

    def output_dialog_geo(self):
        """Manages dialog for setting output filename"""
        self.lineEdit_output.clear()
        self.filename, self.encoding = save_dialog_geo()
        if self.filename is None:
            return
        self.lineEdit_output.setText(self.filename)

    def input_dialog_csv(self):
        """Manages dialog for setting input filename"""
        self.lineEdit_csv.setText("")
        self.FieldOriginX.clear()
        self.FieldOriginY.clear()
        self.FieldDestinationX.clear()
        self.FieldDestinationY.clear()
        self.filename, self.encoding = open_dialog()
        if self.filename is None:
            return 0

        try:
            self.csv_data = read_csv(self.filename, self.encoding)

            if len(self.csv_data) > 0:
                columns = list(self.csv_data[0].keys())
                self.FieldOriginX.addItems(columns)
                self.FieldOriginY.addItems(columns)
                self.FieldDestinationX.addItems(columns)
                self.FieldDestinationY.addItems(columns)
            self.lineEdit_csv.setText(self.filename)

            return 0
        except Exception as err:
            QMessageBox.information(
                self.iface.mainWindow(), 'Error',
                "Something went wrong...(See Qgis log for traceback)")
            QgsMessageLog.logMessage(
                f"OSRM-plugin error report :\n {str(err)}",
                level=Qgis.Warning)
            return -1

    def enable_functionnality(self, text):
        """Load preset functionality groups according to text parameter"""
        functions = (
            self.ComboBoxOrigin.setEnabled, self.label_2.setEnabled,
            self.ComboBoxDestination.setEnabled, self.label.setEnabled,
            self.label_5.setEnabled, self.pushButtonCsv.setEnabled,
            self.FieldOriginX.setEnabled, self.FieldOriginY.setEnabled,
            self.FieldDestinationX.setEnabled, self.label_6.setEnabled,
            self.FieldDestinationY.setEnabled, self.label_7.setEnabled,
            self.label_8.setEnabled, self.label_9.setEnabled,
            self.lineEdit_csv.setEnabled
        )
        if 'layer' in text:
            values = (True, True, True, True,
                      False, False, False, False, False,
                      False, False, False, False, False,
                      False)
        elif '.csv' in text:
            values = (False, False, False, False,
                      True, True, True, True, True,
                      True, True, True, True, True,
                      True)
        elif 'method' in text:
            values = (False, False, False, False,
                      False, False, False, False, False,
                      False, False, False, False, False,
                      False)
        else:
            return
        for func, bool_value in zip(functions, values):
            func(bool_value)

    def _prepare_queries(self):
        """Get the coordinates for each viaroute to query"""
        if self.ComboBoxOrigin.isEnabled():
            origin_layer = self.ComboBoxOrigin.currentLayer()
            destination_layer = self.ComboBoxDestination.currentLayer()
            if '4326' not in origin_layer.crs().authid():
                xform = QgsCoordinateTransform(
                    origin_layer.crs(),
                    QgsCoordinateReferenceSystem.fromEpsgId(4326),
                    QgsCoordinateTransformContext()
                )
                origin_ids_coords = \
                    [(ft.id(), xform.transform(ft.geometry().asPoint()))
                     for ft in origin_layer.getFeatures()]
            else:
                origin_ids_coords = \
                    [(ft.id(), ft.geometry().asPoint())
                     for ft in origin_layer.getFeatures()]

            if '4326' not in destination_layer.crs().authid():
                xform = QgsCoordinateTransform(
                    origin_layer.crs(),
                    QgsCoordinateReferenceSystem.fromEpsgId(4326),
                    QgsCoordinateTransformContext()
                )
                destination_ids_coords = \
                    [(ft.id(), xform.transform(ft.geometry().asPoint()))
                     for ft in destination_layer.getFeatures()]
            else:
                destination_ids_coords = \
                    [(ft.id(), ft.geometry().asPoint())
                     for ft in destination_layer.getFeatures()]

            if len(origin_ids_coords) * len(destination_ids_coords) > 100000:
                QMessageBox.information(
                    self.iface.mainWindow(), 'Info',
                    "Too many route to calculate, try with less than 100000")
                return -1

            return [(origin[1][1], origin[1][0], dest[1][1], dest[1][0])
                    for origin in origin_ids_coords
                    for dest in destination_ids_coords]

        if self.FieldOriginX.isEnabled():
            fox = self.FieldOriginX.currentText()
            foy = self.FieldOriginY.currentText()
            fdx = self.FieldDestinationX.currentText()
            fdy = self.FieldDestinationY.currentText()
            queries = []
            for row in self.csv_data:
                queries.append([row[foy], row[fox], row[fdy], row[fdx]])

            return queries

        return -1

    def reverse_origin_destination_batch(self):
        """Helper function to dispatch to the proper method"""
        if self.FieldOriginX.isEnabled():
            self.switch_origin_destination_fields()
        elif self.ComboBoxOrigin.isEnabled():
            self.switch_origin_destination_box()
        else:
            self.switch_origin_destination_fields()
            self.switch_origin_destination_box()

    def switch_origin_destination_fields(self):
        """ Switch the selected fields from the csv file"""
        try:
            oxf = self.FieldOriginX.currentIndex()
            self.FieldOriginX.setCurrentIndex(
                self.FieldDestinationX.currentIndex())
            oyf = self.FieldOriginY.currentIndex()
            self.FieldOriginY.setCurrentIndex(
                self.FieldDestinationY.currentIndex())
            self.FieldDestinationX.setCurrentIndex(oxf)
            self.FieldDestinationY.setCurrentIndex(oyf)
        except Exception as err:
            QgsMessageLog.logMessage(
                f"OSRM-plugin error report :\n {str(err)}",
                level=Qgis.Warning
            )

    def switch_origin_destination_box(self):
        """ Switch the Origin and the Destination layer"""
        try:
            tmp_o = self.ComboBoxOrigin.currentLayer()
            tmp_d = self.ComboBoxDestination.currentLayer()
            self.ComboBoxOrigin.setLayer(tmp_d)
            self.ComboBoxDestination.setLayer(tmp_o)
        except Exception as err:
            QgsMessageLog.logMessage(
                f"OSRM-plugin error report :\n {str(err)}",
                level=Qgis.Warning
            )

    def get_batch_route(self):
        """Query the API and make a line for each route"""
        self.filename = self.lineEdit_output.text()
        is_shape = '.shp' in self.filename
        is_add_layer = self.check_add_layer.isChecked()
        if (not is_shape and not is_add_layer):
            QMessageBox.information(
                self.iface.mainWindow(),
                'Error',
                "Output have to be saved and/or added to the canvas"
            )
            return -1

        self.nb_route, self.errors = 0, 0
        queries = self._prepare_queries()
        try:
            nb_queries = len(queries)
        except TypeError:
            return -1

        if nb_queries < 1:
            QMessageBox.information(
                self.iface.mainWindow(),
                'Info',
                f"Something went wrong append {self.filename}"
                f" - No locations to request"
            )
            return -1

        if nb_queries > 20 and 'routing.openstreetmap.de' in self.base_url:
            QMessageBox.information(
                self.iface.mainWindow(), 'Error',
                "Please, don't make heavy requests on the public API")
            return -1

        self.make_prog_bar()
        self.progress.setValue(5)
        pool = ThreadPool(processes=4 if len(queries) >= 4 else len(queries))

        try:
            features = list(pool.map(self.prep_routes, queries))
            pool.close()
        except ValueError as err:
            self.display_error(err, 1)
            pool.close()
            return -1

        self.progress.setValue(85)

        features = [
            fet
            for fet in features if not (isinstance(fet, int) and fet == -1)
        ]

        if len(features) < 1:
            QMessageBox.information(
                self.iface.mainWindow(),
                'Info',
                f"Something wrong append {self.filename} - No feature fetched"
            )
            return -1

        self.return_batch_route(features)
        self.progress.setValue(95)
        return 0

    def prep_routes(self, query):
        """Fetch and parse route objects from query points"""
        yo, xo, yd, xd = query
        try:
            url = ''.join(
                [
                    self.prepare_request_url(self.base_url, 'route'),
                    f"{xo},{yo};{xd},{yd}?overview=full&steps=false&"
                    f"alternatives=false"
                ]
            )
            if self.api_key:
                url = ''.join([url, '&api_key=', self.api_key])
            parsed = self.query_url(url)
        except (URLError, HTTPError, ContentTooShortError) as err:
            self.display_error(err, 1)
            self.errors += 1

            return -1
        try:
            line_geom = decode_geom(parsed['routes'][0]["geometry"])

        except KeyError:
            self.iface.messageBar().pushMessage(
                "Error",
                f"No route found between {(xo, yo)} and {(xd, yd)}",
                duration=5
            )
            self.errors += 1
            return -1

        fet = QgsFeature()
        fet.setGeometry(line_geom)
        fet.setAttributes([
            self.nb_route,
            parsed['routes'][0]['duration'],
            parsed['routes'][0]['distance']
        ])
        self.nb_route += 1

        return fet

    def return_batch_route(self, features):
        """Save and/or display the routes retrieved"""
        osrm_batch_route_layer = QgsVectorLayer(
            "Linestring?crs=epsg:4326&field=id:integer"
            "&field=total_time:integer(20)&field=distance:integer(20)",
            f"routes_osrm{self.nb_done}",
            "memory"
        )
        provider = osrm_batch_route_layer.dataProvider()
        provider.addFeatures(features)
        QgsProject.instance().addMapLayer(osrm_batch_route_layer)

        opt = QgsVectorFileWriter.SaveVectorOptions()
        opt.actionOnExistingFile = \
            QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile
        opt.driverName = "ESRI Shapefile"
        opt.fileEncoding = self.encoding

        if self.filename:
            error = QgsVectorFileWriter.writeAsVectorFormatV3(
                osrm_batch_route_layer,
                self.filename,
                QgsCoordinateTransformContext(),
                opt
            )
            if error[0] != QgsVectorFileWriter.NoError:
                self.iface.messageBar().pushMessage(
                    "Error",
                    f"Can't save the result into {self.filename} - "
                    f"Output have been added to the canvas (see QGis log "
                    f"for error traceback)",
                    duration=10
                )
                QgsMessageLog.logMessage(
                    f"OSRM-plugin error report :\n {error}",
                    level=Qgis.Warning
                )
                self.iface.setActiveLayer(osrm_batch_route_layer)
                return -1
            QMessageBox.information(
                self.iface.mainWindow(), 'Info',
                f"Result saved in {self.filename}")
        if self.check_add_layer.isChecked():
            self.iface.setActiveLayer(osrm_batch_route_layer)
        else:
            QgsProject.instance().removeMapLayer(
                osrm_batch_route_layer.id())
        self.iface.messageBar().clearWidgets()
        return 0
