**OSRM Routing plugin for QGIS 3.44**

Routing with OSRM
=================
This plugin is available for QGIS version 3.44 and is under active development.
Plugin source code is available at https://github.com/strues-maps/qgis_osrm .
This plugin is licensed under GNU GPL v2.0 or later.
 
This plugin was developed by porting relevant parts from osrm-qgis-plugin for
QGIS2 by Matthieu Viry. QGIS2 plugin was available at https://github.com/mthh/osrm-qgis-plugin .

TODO
====
- create an url and api key configuration window;
- support QGIS 3.42, 3.40, and older versions;
- add export distances option in route matrix;
- redraw layers after base route is removed
- redraw layers after isochrones are removed
- redraw layers after traveling salesman routes are removed
- remove traveling salesman markers layer on clear previous
- write units tests

INHERITED TODO
==============
- ensure that the MapToolEmitPoint is unset when the plugin window is closed
- batch route calculation - implement load csv file with origins and destinations
- prep_instruction - itineraries window for route

PREPARE DEVELOPMENT ENVIRONMENT
===============================
```
sudo apt install qttools5-dev-tools pyqt5-dev-tools pylint pycodestyle python3-scipy python3-matplotlib python3-numpy python3-shapely python3-qgis
sudo pip install qgis-plugin-ci --break-system-packages
```

EXAMPLES
========


FOUND A BUG?
===================================
If you found a bug, feel free to report it at https://github.com/strues-maps/qgis_osrm/issues


COMMERCIAL SUPPORT AND IMPROVEMENTS
===================================

In case you need commercial support for this plugin, feel free to contact current
developer via e-mail at info@strues-maps.lt, subject - qgis osrm plugin.