# -*- coding: utf-8 -*-
"""
/***************************************************************************
 OSRMDialog
                                 A QGIS plugin
 Find a route with OSRM
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
from urllib.error import URLError, HTTPError, ContentTooShortError
from PyQt5 import QtGui, uic
from PyQt5.QtWidgets import QDialog
from qgis.gui import QgsMapToolEmitPoint  # pylint: disable = no-name-in-module
from qgis.core import (  # pylint: disable = no-name-in-module
    QgsFeature, QgsProject, QgsVectorLayer, QgsPoint,
    QgsGeometry, QgsRuleBasedRenderer, QgsSymbol, QgsSingleSymbolRenderer
)
from .osrm_utils import (
    decode_geom, prepare_route_symbol, put_on_top, encode_to_polyline
)
from .template_osrm import TemplateOsrm


FORM_CLASS_DIALOG_BASE, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui/osrm_dialog_base.ui'))


class OSRMDialog(QDialog, FORM_CLASS_DIALOG_BASE, TemplateOsrm):
    """Route retrieval dialog"""

    def __init__(self, iface, parent=None):
        """Constructor."""
        super().__init__(parent)
        TemplateOsrm.__init__(self)

        self.setupUi(self)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.origin_emit = QgsMapToolEmitPoint(self.canvas)
        self.intermediate_emit = QgsMapToolEmitPoint(self.canvas)
        self.destination_emit = QgsMapToolEmitPoint(self.canvas)
        self.nb_route = 0
        self.intermediate = []
        self.pushButtonTryIt.clicked.connect(self.get_route)
        self.pushButtonReverse.clicked.connect(self.reverse_origin_destination)
        self.pushButtonClear.clicked.connect(self.clear_all_single)
        self.close_button_box.clicked.connect(self.close_button_clicked)
        self.parsed = None
        self.destination = None
        self.nb_alternative = None
        self.load_providers()

    def closeEvent(self, event):  # pylint: disable=invalid-name
        """Handle window close event"""
        self.canvas.unsetMapTool(self.origin_emit)
        self.canvas.unsetMapTool(self.intermediate_emit)
        self.canvas.unsetMapTool(self.destination_emit)
        super().closeEvent(event)

    def close_button_clicked(self):
        """Handle close button in dialog event"""
        self.canvas.unsetMapTool(self.origin_emit)
        self.canvas.unsetMapTool(self.intermediate_emit)
        self.canvas.unsetMapTool(self.destination_emit)

    def store_intermediate(self, point):
        """Store intermediate points for route"""
        point = self.transform_point_for_storage(self.canvas, point)
        self.intermediate.append(tuple(map(lambda x: round(x, 6), point)))
        self.canvas.unsetMapTool(self.intermediate_emit)
        self.lineEdit_xyI.setText(str(self.intermediate))

    def store_destination(self, point):
        """Store destination point for route"""
        self.destination = self.transform_point_for_storage(self.canvas, point)
        self.canvas.unsetMapTool(self.destination_emit)
        self.lineEdit_xyD.setText(
            self.transform_point_to_str(self.destination)
        )

    def get_alternatives(self, provider):
        """
        Fetch the geometry of alternatives roads if requested
        """
        for i, alt_geom in enumerate(self.parsed['routes'][1:]):
            decoded_alt_line = decode_geom(alt_geom["geometry"])
            fet = QgsFeature()
            fet.setGeometry(decoded_alt_line)
            fet.setAttributes([
                i + 1,
                alt_geom["duration"],
                alt_geom["distance"]
            ])
            provider.addFeatures([fet])

    def reverse_origin_destination(self):
        """Swap origin and destination"""
        tmp = self.lineEdit_xyO.text()
        tmp1 = self.lineEdit_xyD.text()
        self.lineEdit_xyD.setText(str(tmp))
        self.lineEdit_xyO.setText(str(tmp1))

    def clear_all_single(self):
        """Clear all single route points"""
        self.lineEdit_xyO.setText('')
        self.lineEdit_xyD.setText('')
        self.lineEdit_xyI.setText('')
        self.intermediate = []
        needs_repaint = False

        for layer in QgsProject.instance().mapLayers():
            if 'route_osrm' in layer:
                QgsProject.instance().removeMapLayer(layer)
                needs_repaint = True
            if 'markers_osrm' in layer:
                QgsProject.instance().removeMapLayer(layer)
                needs_repaint = True
            if 'instruction_single_osrm' in layer:
                QgsProject.instance().removeMapLayer(layer)
                needs_repaint = True
        if needs_repaint:
            self.repaint_layers()
        self.nb_route = 0

    def prep_instruction(self, nb_route, routes_json, alt=None):
        """
        Prepare the instruction layer, each field corresponding to an OSRM
        viaroute response field.
        """
        osrm_instruction_layer = QgsVectorLayer(
            "Point?crs=epsg:4326&field=id:integer&field=alt:integer"
            "&field=maneuver_bearing_before:integer"
            "&field=bearing_after:integer"
            "&field=maneuver_type:string(254)"
            "&field=maneuver_modifier:string(254)"
            "&field=maneuver_exit:integer(20)"
            "&field=street_name:string(254)"
            "&field=length_m:string(254)&field=route_idx:integer(20)"
            "&field=time_min:string(254)",
            f"instruction_single_osrm{nb_route}",
            "memory")
        provider = osrm_instruction_layer.dataProvider()

        nbi = 0
        features = []
        for route_idx, route in enumerate(routes_json):
            for leg in route["legs"]:
                for step in leg["steps"]:
                    if "maneuver" not in step:
                        continue
                    if "location" not in step["maneuver"]:
                        continue

                    maneuver = step["maneuver"]
                    coords = maneuver["location"]
                    fet = QgsFeature()
                    pt = QgsPoint(coords[0], coords[1])
                    fet.setGeometry(QgsGeometry.fromPoint(pt))
                    fet.setAttributes(
                        [
                            nbi,
                            alt if alt is not None else 0,
                            maneuver["bearing_before"]
                            if "bearing_before" in maneuver else None,
                            maneuver["bearing_after"]
                            if "bearing_after" in maneuver else None,
                            step["maneuver"]["type"]
                            if "type" in maneuver else None,
                            step["maneuver"]["modifier"]
                            if "modifier" in maneuver else None,
                            step["maneuver"]["exit"]
                            if "exit" in maneuver else None,
                            step["name"],
                            step["distance"],
                            route_idx,
                            step["duration"] / 60
                        ]
                    )
                    features.append(fet)
                    nbi += 1
            if (alt is None) and (route_idx > 0):
                break
        provider.addFeatures(features)

        symbol = QgsSymbol.defaultSymbol(osrm_instruction_layer.geometryType())
        symbol.setSize(2)
        symbol.setColor(QtGui.QColor("#d9ef8b"))
        osrm_instruction_layer.setRenderer(QgsSingleSymbolRenderer(symbol))

        return provider, osrm_instruction_layer

    @staticmethod
    def make_origin_destination_markers(nb, xo, yo, xd, yd, list_coords=None):
        """
        Prepare the Origin (green), Destination (red) and Intermediates (grey)
        markers.
        """
        origin_destination_layer = QgsVectorLayer(
            "Point?crs=epsg:4326&field=id_route:integer&field=role:string(80)",
            f"markers_osrm{nb}", "memory")
        features = []
        fet = QgsFeature()
        fet.setGeometry(QgsGeometry.fromPoint(QgsPoint(float(xo), float(yo))))
        fet.setAttributes([nb, 'Origin'])
        features.append(fet)
        fet = QgsFeature()
        fet.setGeometry(QgsGeometry.fromPoint(QgsPoint(float(xd), float(yd))))
        fet.setAttributes([nb, 'Destination'])
        features.append(fet)
        marker_rules = [
            ('Origin', '"role" LIKE \'Origin\'', '#50b56d', 4),
            ('Destination', '"role" LIKE \'Destination\'', '#d31115', 4),
        ]
        if list_coords:
            for i, pt in enumerate(list_coords):
                fet = QgsFeature()
                fet.setGeometry(
                    QgsGeometry.fromPoint(QgsPoint(float(pt[0]), float(pt[1])))
                )
                fet.setAttributes([nb, f"Via point n°{i}"])
                features.append(fet)

            marker_rules.insert(
                1, ('Intermediate', '"role" LIKE \'Via point%\'', 'grey', 2)
            )
        origin_destination_layer.dataProvider().addFeatures(features)

        symbol = QgsSymbol.defaultSymbol(
            origin_destination_layer.geometryType()
        )
        renderer = QgsRuleBasedRenderer(symbol)
        root_rule = renderer.rootRule()
        for label, expression, color_name, size in marker_rules:
            rule = root_rule.children()[0].clone()
            rule.setLabel(label)
            rule.setFilterExpression(expression)
            rule.symbol().setColor(QtGui.QColor(color_name))
            rule.symbol().setSize(size)
            root_rule.appendChild(rule)

        root_rule.removeChildAt(0)
        origin_destination_layer.setRenderer(renderer)
        return origin_destination_layer

    def get_route(self):
        """
        Main method to prepare the request and display the result on the
        QGIS canvas.
        """
        origin = self.lineEdit_xyO.text()
        interm = self.lineEdit_xyI.text()
        destination = self.lineEdit_xyD.text()

        try:
            assert match('^[^a-zA-Z]+$', origin) and 46 > len(origin) > 4
            assert (
               match('^[^a-zA-Z]+$', destination)
               and 46 > len(destination) > 4
            )
            xo, yo = self.transform_str_to_coords(origin)
            xd, yd = self.transform_str_to_coords(destination)
        except AssertionError:
            self.iface.messageBar().pushMessage(
                "Error", "Invalid coordinates !", duration=10)
            return -1

        alternative = str(self.checkBox_alternative.isChecked()).lower()
        steps = str(self.checkBox_instructions.isChecked()).lower()

        if interm:
            try:
                assert match('^[^a-zA-Z]+$', interm) and 150 > len(interm) > 4
                interm = self.transform_str_to_coords_list(interm)
                tmp = ';'.join([f"{xi},{yi}" for xi, yi in interm])
                url = ''.join([
                    self.prepare_request_url(self.base_url, 'route'),
                    f"{xo},{yo};", tmp, f";{xd},{yd}",
                    f"?overview=full&alternatives={alternative}&steps={steps}"
                ])
            except AssertionError:
                self.iface.messageBar().pushMessage(
                    "Error",
                    "Invalid intemediates coordinates",
                    duration=10
                )
                return -1
        else:
            url = ''.join([
                self.prepare_request_url(self.base_url, 'route'),
                "polyline(", encode_to_polyline([(yo, xo), (yd, xd)]), ")",
                f"?overview=full&alternatives={alternative}&steps={steps}"
            ])

        if self.api_key:
            url = ''.join([url, '&api_key=', self.api_key])
        print(f"Fetch route query: {url}")

        try:
            self.parsed = self.query_url(url)
            assert "code" in self.parsed
        except (
            URLError,
            HTTPError,
            ContentTooShortError,
            AssertionError
        ) as err:
            self.display_error(err, 1)
            return -1

        if 'Ok' not in self.parsed['code']:
            self.display_error(self.parsed['code'], 1)
            return -1

        try:
            enc_line = self.parsed['routes'][0]["geometry"]
            line_geom = decode_geom(enc_line)
        except KeyError:
            self.iface.messageBar().pushMessage(
                "Error",
                f"No route found between {origin} and {destination}",
                duration=5)
            return -1

        self.nb_route += 1
        osrm_route_layer = QgsVectorLayer(
            "Linestring?crs=epsg:4326&field=id:integer"
            "&field=total_time:integer(20)&field=distance:integer(20)",
            f"route_osrm{self.nb_route}", "memory")
        my_symb = prepare_route_symbol(self.nb_route)
        osrm_route_layer.setRenderer(QgsSingleSymbolRenderer(my_symb))

        provider = osrm_route_layer.dataProvider()
        features = []
        for i, route in enumerate(self.parsed["routes"]):
            enc_line = route["geometry"]
            line_geom = decode_geom(enc_line)
            fet = QgsFeature()
            fet.setGeometry(line_geom)
            fet.setAttributes([
                i,
                route["duration"],
                route["distance"]
            ])
            features.append(fet)
            if not self.checkBox_alternative.isChecked():
                break
        provider.addFeatures(features)

        origin_destination_layer = self.make_origin_destination_markers(
            self.nb_route,
            xo,
            yo,
            xd,
            yd,
            interm
        )
        QgsProject.instance().addMapLayer(origin_destination_layer)

        osrm_route_layer.updateExtents()
        QgsProject.instance().addMapLayer(osrm_route_layer)
        self.iface.setActiveLayer(osrm_route_layer)
        self.iface.zoomToActiveLayer()

        put_on_top(origin_destination_layer.id(), osrm_route_layer.id())

        if self.checkBox_instructions.isChecked():
            _, instruct_layer = self.prep_instruction(
                self.nb_route,
                self.parsed["routes"],
                self.checkBox_alternative.isChecked())
            QgsProject.instance().addMapLayer(instruct_layer)
            self.iface.setActiveLayer(instruct_layer)
            put_on_top(instruct_layer.id(), origin_destination_layer.id())
        return 0
