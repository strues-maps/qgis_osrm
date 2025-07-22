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
    QgsExpressionContextUtils
)


def qgis_version_less_than(v):
    """Compare current QGIS version with one provided as parameter"""
    version = QgsExpressionContextUtils.globalScope().variable('qgis_version')
    current_major, current_minor = version.split('.')[0:2]
    ref_major, ref_minor = v.split('.')[0:2]

    return (current_major, current_minor) < (ref_major, ref_minor)


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
