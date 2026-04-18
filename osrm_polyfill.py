# -*- coding: utf-8 -*-
"""
/***************************************************************************
 qgis polyfill function
                                 A QGIS plugin
 wrapper for calling functions and enums not available in QGIS 3.28
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


from qgis.core import (  # pylint: disable=no-name-in-module
    QgsExpressionContextUtils, QgsPointXY, QgsGeometry
)
import matplotlib
import qgis.PyQt.QtCore


def is_version_less_than(current, reference):
    """Compare two versions"""
    current_major, current_minor = current.split('.')[0:2]
    current_major = int(current_major)
    current_minor = int(current_minor)
    ref_major, ref_minor = reference.split('.')[0:2]
    ref_major = int(ref_major)
    ref_minor = int(ref_minor)

    return (current_major, current_minor) < (ref_major, ref_minor)


def qgis_version_less_than(reference):
    """Compare current QGIS version with one provided as parameter"""
    current = QgsExpressionContextUtils.globalScope().variable('qgis_version')
    return is_version_less_than(current, reference)


def pyqt_version_less_than(reference):
    """Compare current PyQt version with one provided as parameter"""
    current = qgis.PyQt.QtCore.QT_VERSION_STR
    return is_version_less_than(current, reference)


def matplotlib_version_less_than(reference):
    """Compare current QGIS version with one provided as parameter"""
    current = matplotlib.__version__
    return is_version_less_than(current, reference)


def Qgis_GeometryType_Line():  # pylint: disable=invalid-name
    """Polyfill for Qgis.GeometryType.Line"""
    if qgis_version_less_than('3.30'):
        return 1

    from qgis.core import Qgis  # pylint: disable=no-name-in-module
    return Qgis.GeometryType.Line


def Qgis_GeometryType_Point():  # pylint: disable=invalid-name
    """Polyfill for Qgis.GeometryType.Point"""
    if qgis_version_less_than('3.30'):
        return 0

    from qgis.core import Qgis  # pylint: disable=no-name-in-module
    return Qgis.GeometryType.Point


def Qgis_QMessageBox_Icon_Information():  # pylint: disable=invalid-name
    """Polyfill for QMessageBox.Icon.Information"""
    # pylint: disable=line-too-long
    from qgis.PyQt.QtWidgets import QMessageBox  # noqa

    if pyqt_version_less_than('6.0'):
        return QMessageBox.Information

    return QMessageBox.Icon.Information


def Qgis_QMessageBox_Icon_Warning():  # pylint: disable=invalid-name
    """Polyfill for QMessageBox.Icon.Warning"""
    from qgis.PyQt.QtWidgets import QMessageBox  # noqa

    if pyqt_version_less_than('6.0'):
        return QMessageBox.Warning

    return QMessageBox.Icon.Warning


def Qt_TextFormat_RichText():  # pylint: disable=invalid-name
    """Polyfill for Qt.TextFormat.RichText"""
    from qgis.PyQt.QtCore import Qt  # pylint: disable=no-name-in-module

    if pyqt_version_less_than('6.0'):
        return Qt.RichText

    return Qt.TextFormat.RichText


def QFileDialog_FileMode_AnyFile():  # pylint: disable=invalid-name
    """Polyfill for QFileDialog.FileMode.AnyFile"""
    from qgis.PyQt.QtWidgets import QFileDialog

    if pyqt_version_less_than('6.0'):
        return QFileDialog.AnyFile

    return QFileDialog.FileMode.AnyFile


def QFileDialog_AcceptMode_AcceptOpen():  # pylint: disable=invalid-name
    """Polyfill for QFileDialog.AcceptMode.AcceptOpen"""
    from qgis.PyQt.QtWidgets import QFileDialog

    if pyqt_version_less_than('6.0'):
        return QFileDialog.AcceptOpen

    return QFileDialog.AcceptMode.AcceptOpen


def QFileDialog_AcceptMode_AcceptSave():  # pylint: disable=invalid-name
    """Polyfill for QFileDialog.AcceptMode.AcceptSave"""
    from qgis.PyQt.QtWidgets import QFileDialog

    if pyqt_version_less_than('6.0'):
        return QFileDialog.AcceptSave

    return QFileDialog.AcceptMode.AcceptSave


def Qt_AlignmentFlag_AlignLeft():  # pylint: disable=invalid-name
    """Polyfill for Qt.Alignment.AlignLeft"""
    from qgis.PyQt.QtCore import Qt  # pylint: disable=no-name-in-module

    if pyqt_version_less_than('6.0'):
        return Qt.AlignLeft

    return Qt.AlignmentFlag.AlignLeft


def Qt_AlignmentFlag_AlignVCenter():  # pylint: disable=invalid-name
    """Polyfill for Qt.Alignment.AlignLeft"""
    from qgis.PyQt.QtCore import Qt  # pylint: disable=no-name-in-module

    if pyqt_version_less_than('6.0'):
        return Qt.AlignVCenter

    return Qt.AlignmentFlag.AlignVCenter


def qgsgeom_from_mpl_contour(contour_set):
    """Convert MatPlotLib polygons to QgsGeometry polygons"""
    if matplotlib_version_less_than('3.9'):
        polygons = []
        for path_collection in contour_set.collections:
            mpoly = []
            for path in path_collection.get_paths():
                path.should_simplify = False
                poly = path.to_polygons()
                if len(poly) > 0 and len(poly[0]) > 3:
                    exterior = [QgsPointXY(*p.tolist()) for p in poly[0]]
                    mpoly.append([exterior])
            if len(mpoly) == 1:
                polygons.append(QgsGeometry.fromPolygonXY(mpoly[0]))
            else:
                polygons.append(QgsGeometry.fromPolygonXY([]))
    else:
        polygons = []
        for path in contour_set.get_paths():
            mpoly = []
            path.should_simplify = False
            poly = path.to_polygons()
            if len(poly) > 0 and len(poly[0]) > 3:
                exterior = [QgsPointXY(*p.tolist()) for p in poly[0]]
                mpoly = [exterior]
            if len(mpoly) == 1:
                polygons.append(QgsGeometry.fromPolygonXY(mpoly))
            else:
                polygons.append(QgsGeometry.fromPolygonXY([]))
    return polygons
