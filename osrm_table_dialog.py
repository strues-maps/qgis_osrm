# -*- coding: utf-8 -*-
"""
/***************************************************************************
 OSRMTableDialog
                                 A QGIS plugin
 Route distance/time table
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
import csv
import sys
from codecs import open as codecs_open
import numpy as np
from PyQt5 import uic
from PyQt5.QtWidgets import QMessageBox, QDialog
from qgis.core import (  # pylint: disable = no-name-in-module
    QgsMapLayerProxyModel, QgsFieldProxyModel, QgsMessageLog, Qgis
)
from .osrm_utils import get_coords_ids, save_dialog, fetch_table
from .template_osrm import TemplateOsrm


FORM_CLASS_TABLE_DIALOG_BASE, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui/osrm_table_dialog_base.ui'))


class OSRMTableDialog(QDialog, FORM_CLASS_TABLE_DIALOG_BASE, TemplateOsrm):
    """Dialog for route distance/time table"""

    def __init__(self, iface, parent=None):
        """Constructor."""
        super().__init__(parent)
        TemplateOsrm.__init__(self)

        self.setupUi(self)
        self.iface = iface
        self.encoding = "System"
        self.pushButton_fetch.setDisabled(True)
        self.comboBox_layer.setFilters(QgsMapLayerProxyModel.PointLayer)

        id_field_filter = (
            QgsFieldProxyModel.Double | QgsFieldProxyModel.Int |
            QgsFieldProxyModel.LongLong | QgsFieldProxyModel.Numeric |
            QgsFieldProxyModel.String
        )
        self.comboBox_idfield_2.setFilters(id_field_filter)
        self.comboBox_idfield.setFilters(id_field_filter)

        self.comboBox_layer.layerChanged.connect(
            self.comboBox_idfield.setLayer
        )
        self.lineEdit_output.textChanged.connect(
            lambda x: self.pushButton_fetch.setEnabled(True)
            if '.csv' in x else self.pushButton_fetch.setDisabled(True)
        )
        self.comboBox_layer_2.setFilters(
            QgsMapLayerProxyModel.PointLayer
        )
        self.comboBox_layer_2.layerChanged.connect(
            self.comboBox_idfield_2.setLayer
        )
        self.pushButton_browse.clicked.connect(self.output_dialog)
        self.pushButton_fetch.clicked.connect(self.get_table)
        self.filename = None
        self.encoding = None
        self.load_providers()

    def output_dialog(self):
        """
        Dialog for setting filename and encoding for route distance/time table
        """
        self.lineEdit_output.clear()
        self.filename, self.encoding = save_dialog()
        if self.filename is None:
            return
        self.lineEdit_output.setText(self.filename)

    def get_table(self):
        """
        Main method to prepare the query and fecth the table to a .csv file
        """
        self.filename = self.lineEdit_output.text()

        s_layer = self.comboBox_layer.currentLayer()

        if self.comboBox_layer_2.currentLayer() != s_layer:
            d_layer = self.comboBox_layer_2.currentLayer()
            coords_dest, ids_dest = get_coords_ids(
                d_layer,
                self.comboBox_idfield_2.currentField()
            )
        else:
            d_layer = None
            coords_dest = None
            ids_dest = None

        coords_src, ids_src = get_coords_ids(
            s_layer,
            self.comboBox_idfield.currentField()
        )

        url = self.prepare_request_url(self.base_url, 'table')

        try:
            table = fetch_table(url, self.api_key, coords_src, coords_dest)
        except ValueError as err:
            self.display_error(err, 1)
            return -1

        table_durations = table[0]

        # Convert the matrix in minutes if needed :
        if self.checkBox_minutes.isChecked():
            table_durations = (table_durations / 60.0).round(2)

        # Replace the value corresponding to a not-found connection :
        if self.checkBox_empty_val.isChecked():
            if self.checkBox_minutes.isChecked():
                table_durations[table_durations == 3579139.4] = np.NaN
            else:
                table_durations[table_durations == 2147483647] = np.NaN

        # Fetch the default encoding if selected :
        if self.encoding == "System":
            self.encoding = sys.getdefaultencoding()

        # Write the result in csv :
        try:
            with codecs_open(self.filename, 'w', self.encoding) as out_file:
                writer = csv.writer(out_file, lineterminator='\n')
                if self.checkBox_flatten.isChecked():
                    table_durations = table_durations.ravel()
                    if d_layer:
                        idsx = [(i, j) for i in ids_src for j in ids_dest]
                    else:
                        idsx = [(i, j) for i in ids_src for j in ids_src]
                    writer.writerow(['Origin', 'Destination', 'Time'])
                    writer.writerows([
                        [idsx[i][0], idsx[i][1], table_durations[i]]
                        for i in range(len(idsx))
                    ])
                else:
                    table_list = table_durations.tolist()
                    if d_layer:
                        writer.writerow([''] + ids_dest)
                        writer.writerows(
                            [
                                [ids_src[_id]] + line
                                for _id, line in enumerate(table_list)
                            ]
                        )
                    else:
                        writer.writerow([''] + ids_src)
                        writer.writerows(
                            [
                                [ids_src[_id]] + line
                                for _id, line in enumerate(table_list)
                            ]
                        )
                out_file.close()
                QMessageBox.information(
                    self.iface.mainWindow(), 'Done',
                    f"OSRM table saved in {self.filename}")
        except Exception as err:
            QMessageBox.information(
                self.iface.mainWindow(), 'Error',
                "Something went wrong...(See Qgis log for traceback)")
            QgsMessageLog.logMessage(
                f"OSRM-plugin error report :\n {str(err)}",
                level=Qgis.Warning)
            return -1

        return 0
