# -*- coding: utf-8 -*-
"""
/***************************************************************************
 OSRM
                                 A QGIS plugin
 Display your routing results from OSRM
                              -------------------
        begin                : 2015-10-29
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

import os.path
from qgis.utils import iface
from PyQt5.QtCore import QTranslator, QCoreApplication, QSettings
from PyQt5.QtWidgets import QAction
from PyQt5.QtGui import QIcon
from .osrm_dialog import OSRMDialog
from .osrm_table_dialog import OSRMTableDialog
from .osrm_access_dialog import OSRMAccessDialog
from .osrm_dialog_tsp import OSRMDialogTSP
from .osrm_batch_route_dialog import OSRMBatchRouteDialog


class OsrmPlugin:
    """QGIS Plugin Implementation."""

    def __init__(self, qgis_iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        self.dlg = None
        # Save reference to the QGIS interface
        self.qgis_iface = qgis_iface
        self.canvas = qgis_iface.mapCanvas()
        # initialize plugin directory
        plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(plugin_dir, 'i18n', f"OSRM_{locale}.qm")

        if os.path.exists(locale_path):
            translator = QTranslator()
            translator.load(locale_path)
            QCoreApplication.installTranslator(translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr('&Routing with OSRM')

        self.toolbar = self.qgis_iface.addToolBar('Routing with OSRM')
        self.toolbar.setObjectName('Routing with OSRM')
    # noinspection PyMethodMayBeStatic

    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('Routing with OSRM', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        add_to_toolbar=True,
        parent=None
    ):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(True)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        self.qgis_iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)

        return action

    def initGui(self):  # pylint: disable=invalid-name
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        self.add_action(
            ':/plugins/qgis-osrm/img/icon.png',
            text=self.tr('Find a route with OSRM'),
            callback=self.run_route,
            parent=self.qgis_iface.mainWindow()
        )

        self.add_action(
            ':/plugins/qgis-osrm/img/icon_table.png',
            text=self.tr('Get a time matrix with OSRM'),
            callback=self.run_table,
            parent=self.qgis_iface.mainWindow(),
        )

        self.add_action(
            ':/plugins/qgis-osrm/img/icon_access.png',
            text=self.tr('Make accessibility isochrones with OSRM'),
            callback=self.run_accessibility,
            parent=self.qgis_iface.mainWindow(),
        )

        self.add_action(
            None,
            text=self.tr('Solve the Traveling Salesman Problem with OSRM'),
            callback=self.run_tsp,
            parent=self.qgis_iface.mainWindow(),
            add_to_toolbar=False,
        )

        self.add_action(
            None,
            text=self.tr('Export many routes from OSRM'),
            callback=self.run_batch_route,
            parent=self.qgis_iface.mainWindow(),
            add_to_toolbar=False,
        )  # ':/plugins/OSRM/img/icon_batchroute.png'

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.qgis_iface.removePluginWebMenu(
                self.tr('&Routing with OSRM'),
                action)
            self.qgis_iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def run_route(self):
        """Run the window to compute a single viaroute"""
        self.dlg = OSRMDialog(iface)
        self.dlg.origin_emit.canvasClicked.connect(
            self.dlg.store_origin
        )
        self.dlg.intermediate_emit.canvasClicked.connect(
            self.dlg.store_intermediate
        )
        self.dlg.destination_emit.canvasClicked.connect(
            self.dlg.store_destination
        )
        self.dlg.pushButtonOrigin.clicked.connect(self.get_origin)
        self.dlg.pushButtonIntermediate.clicked.connect(self.get_intermediate)
        self.dlg.pushButtonDest.clicked.connect(self.get_destination)
        self.dlg.pushButton_about.clicked.connect(self.dlg.print_about)
        self.dlg.show()

    def run_batch_route(self):
        """Run the window to compute many viaroute"""

        if self.dlg is not None:
            self.dlg.nb_done = 0

        self.dlg = OSRMBatchRouteDialog(iface)
        self.dlg.pushButton_about.clicked.connect(self.dlg.print_about)
        self.dlg.show()

    def run_table(self):
        """Run the window for the table function"""
        self.dlg = OSRMTableDialog(iface)
        self.dlg.pushButton_about.clicked.connect(self.dlg.print_about)
        self.dlg.show()

    def run_tsp(self):
        """Run the window for making accessibility isochrones"""
        self.dlg = OSRMDialogTSP(iface)
        self.dlg.pushButton_about.clicked.connect(self.dlg.print_about)
        self.dlg.show()

    def run_accessibility(self):
        """Run the window for making accessibility isochrones"""
        self.dlg = OSRMAccessDialog(iface)
        self.dlg.intermediate_emit.canvasClicked.connect(
            self.dlg.store_intermediate_acces
        )
        self.dlg.pushButtonIntermediate.clicked.connect(self.get_intermediate)
        self.dlg.pushButton_about.clicked.connect(self.dlg.print_about)
        self.dlg.show()

    def get_origin(self):
        """
        Activate map tool for emiting an origin point when clicking
        on map
        """
        self.canvas.setMapTool(self.dlg.origin_emit)

    def get_destination(self):
        """
        Activate map tool for emiting a destination point when clicking
        on map
        """
        self.canvas.setMapTool(self.dlg.destination_emit)

    def get_intermediate(self):
        """
        Activate map tool for emiting an intermediate point when clicking
        on map
        """
        self.canvas.setMapTool(self.dlg.intermediate_emit)
