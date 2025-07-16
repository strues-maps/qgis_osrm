# -*- coding: utf-8 -*-
"""
 This script initializes the plugin, making it known to QGIS.
"""


def classFactory(iface):  # pylint: disable=invalid-name
    """
    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .osrm_plugin import OsrmPlugin

    return OsrmPlugin(iface)
