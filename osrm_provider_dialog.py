# -*- coding: utf-8 -*-
"""
/***************************************************************************
 OSRMProviderDialog
                                 A QGIS plugin
 Provider configuration dialog
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
from PyQt5 import uic
from PyQt5.QtWidgets import QMessageBox, QInputDialog, QDialog
from .template_osrm import TemplateOsrm
from .osrm_utils import read_providers_config, write_providers_config


FORM_CLASS_PROVIDER_DIALOG_BASE, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui/osrm_provider_dialog.ui'))


class OSRMProviderDialog(
    QDialog,
    FORM_CLASS_PROVIDER_DIALOG_BASE,
    TemplateOsrm
):
    """Dialog for provider configuration"""
    def __init__(self, iface, parent=None):
        """Constructor."""
        super().__init__(parent)
        TemplateOsrm.__init__(self)

        self.setupUi(self)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.provider_name = None
        self.push_button_new.clicked.connect(self.new_provider)
        self.push_button_save.clicked.connect(self.save_provider)
        self.push_button_delete.clicked.connect(self.delete_provider)
        self.load_providers()

    def new_provider(self):
        """Handle new provider button action"""
        name, is_submitted = QInputDialog.getText(
            self,
            "Provider name",
            "Enter new provider name:"
        )

        if not is_submitted:
            # canceled new provider creation
            return -1

        if is_submitted and name == '':
            QMessageBox.information(
                self.iface.mainWindow(),
                'Error',
                "Provider name must not be empty")
            return -1

        for provider in self.providers:
            if provider["name"] == name:
                QMessageBox.information(
                    self.iface.mainWindow(),
                    'Error',
                    "Provider name must be unique")
                return -1

        self.providers.append({"name": name, "base_url": "", "api_key": ""})
        write_providers_config(self.providers)
        self.populate_combo_box_provider()

        return 0

    def save_provider(self):
        """Handle save provider action"""
        provider_index = self.combo_box_provider.currentIndex()
        name = self.line_edit_name.text()
        if provider_index > 0:
            if len(name) == 0:
                QMessageBox.information(
                    self.iface.mainWindow(),
                    'Error',
                    "Provider name must not be empty")
                return -1
            for i, provider in enumerate(self.providers):
                if (i != provider_index - 1) and (provider["name"] == name):
                    QMessageBox.information(
                        self.iface.mainWindow(),
                        'Error',
                        "Provider name must be unique")
                    return -1

            provider = self.providers[provider_index - 1]
            self.provider_name = self.line_edit_name.text()
            provider["name"] = self.provider_name
            provider["api_key"] = self.line_edit_api_key.text()
            provider["base_url"] = self.line_edit_base_url.text()
            write_providers_config(self.providers)
            self.populate_combo_box_provider()

        return 0

    def delete_provider(self):
        """Handle delete provider action"""
        provider_index = self.combo_box_provider.currentIndex()
        if provider_index > 0:
            del self.providers[provider_index - 1]
            write_providers_config(self.providers)
            self.populate_combo_box_provider()

    def provider_changed(self):
        """Handle provider selection action"""
        provider_index = self.combo_box_provider.currentIndex()
        if provider_index > 0:
            provider = self.providers[provider_index - 1]
            self.provider_name = provider["name"]
            self.line_edit_name.setText(provider["name"])
            self.line_edit_name.setEnabled(True)
            self.line_edit_base_url.setText(provider["base_url"])
            self.line_edit_base_url.setEnabled(True)
            self.line_edit_api_key.setText(provider["api_key"])
            self.line_edit_api_key.setEnabled(True)
            self.push_button_save.setEnabled(True)
            self.label_2.setEnabled(True)
            self.label_3.setEnabled(True)
            self.label_4.setEnabled(True)
            self.push_button_delete.setEnabled(True)
        else:
            self.provider_name = None
            self.line_edit_name.setText("")
            self.line_edit_name.setEnabled(False)
            self.line_edit_base_url.setText("")
            self.line_edit_base_url.setEnabled(False)
            self.line_edit_api_key.setText("")
            self.line_edit_api_key.setEnabled(False)
            self.push_button_save.setEnabled(False)
            self.label_2.setEnabled(False)
            self.label_3.setEnabled(False)
            self.label_4.setEnabled(False)
            self.push_button_delete.setEnabled(False)

    def populate_combo_box_provider(self):
        """Populates combo box with provider names"""
        try:
            provider_index = self.combo_box_provider.currentIndex()
            provider_index = max(0, provider_index)
            self.providers = read_providers_config()
            names = ["Select provider"] + [
                provider["name"]
                for provider in self.providers
            ]
            self.combo_box_provider.clear()
            self.combo_box_provider.addItems(names)
            if provider_index < len(names):
                self.combo_box_provider.setCurrentIndex(provider_index)
        except (AssertionError, ValueError) as err:
            QMessageBox.warning(
                self.iface.mainWindow(),
                'Error',
                f"Invalid providers configuration file! {err}"
            )
            self.providers = []
