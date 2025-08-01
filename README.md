**OSRM Routing plugin for QGIS >=3.28**

Routing with OSRM
=================
This plugin is available for QGIS version >=3.28 and is under active development.
Plugin source code is available at https://github.com/strues-maps/qgis_osrm .
This plugin is licensed under GNU GPL v2.0 or later.

This plugin was developed by porting relevant parts from osrm-qgis-plugin for
QGIS2 by Matthieu Viry. QGIS2 plugin was available at https://github.com/mthh/osrm-qgis-plugin .

Prepare environment
===============================
User environment uses the following packages:
```
sudo apt install python3-scipy python3-matplotlib python3-numpy python3-shapely python3-qgis
```

Development environment uses the following packages:
```
sudo apt install qttools5-dev-tools pyqt5-dev-tools pylint pycodestyle python3-scipy python3-matplotlib python3-numpy python3-shapely python3-qgis
sudo pip install qgis-plugin-ci --break-system-packages
```

Features
========
- Find a route
- Get a time matrix
- Make accessibility isochrones
- Solve the Travelling Salesman Problem
- Compute and export many routes

Examples
========
Images of this page are displayed on OpenStreetMap tiles (© OpenStreetMap contributors) and route computations were done with Open Source Routing Machine.

Set up a provider configuration
------------
**Change the provider configuration used by the OSRM plugin. There are a few provider urls available in the default plugin installation:**

- Local OSRM at port 5000 (used if OSRM is manually installed on localhost)

- OSM DE Bike Routing (used at https://project-osrm.org demo as bike routing OSRM instance)

- OSM DE Foot Routing (used at https://project-osrm.org demo as foot routing OSRM instance)

- OSM DE Car Routing (used at https://project-osrm.org demo as a car routing OSRM instance)

- Strues-Maps Routing (used by https://strues-maps.lt registered users)

Add new provider urls in the configuration window or edit/delete existing providers. Provider urls should work
out of the box, except for "Strues-Maps Routing", which requires setting the API key that users receive
during registration. 

![config illustration](img/config.png)

Find a route
------------
**Display a simple route from OSRM (with support of viapoints, alternative roads, and route instructions)**:

Request a route calculation from the point of origin to the point of destination by clicking on the
*[Origin point]* button and clicking on the map, by clicking on the *[Destination point]* button and clicking on the map, and
optionally by clicking on the *[Intermadiate point]* button and clicking on the map. In case there are multiple intermadiate points,
click on the *[Intermadiate point]* button before each point. Marking "Display routing instructions" will create an additional
instructions layer that contains an attribute table with routing instructions. Marking "Display possible alternative
roads" will include alternative roads in the route layer.

![route illustration](img/fastest_route.png)

Fetch a time-distance matrix
----------------------------
**Get a time matrix from one (or between two) QGIS point layer(s)**:

Request a duration-distance matrix from points in one layer to points in another layer. In the "Source point layer" field, select a layer
from the current project and select an "Source ID field" from that layer. In the "Destination point layer" field, optionally select the same or
another layer from the current project and select an "Destination ID field" from that layer. In the "Metrics to be used" field, choose either
duration to calculate seconds between points, or distance for calculating meters. Marking "Time converted in minutes" will recalculate
durations from seconds to minutes. The default time matrix will have rows as sources and columns as destinations. Marking the "Flatten the matrix"
checkbox will output the matrix in the format: ("Source", "Destination", "Distance/Duration") for each row. To save the calculated
matrix to a file, click the *[Browse]* button, choose a CSV file, and click the *[Fetch and save the result]* button.

![table illustration](img/table.png)

Compute accessibility isochrones
--------------------------------
**Compute monocentric or polycentric accessibility isochrones**:

Request a polycentric access isochrone calculation from points in a Point layer. In the method selection field, select the "By selecting a point
layer" option. In the "Source point layer" select the layer that will be used as isochrone centers. In the "Max. polygon isochrone" field, enter
the maximum time for which the isochrone will be calculated. In the "Intervall" field, enter the step size in the isochrone calculation. 

Request a polycentric access isochrone calculation from points on the map. In the method selection field, select "By clicking on the map". Click on the 
*[Center points]* button and click on the map. In case there are multiple isochrone centers, click *[Center points]* before clicking on the map each time. 
There might be a bug in the project-osrm.org demo instance that prevents isochrones from being calculated, but it works fine with the Local OSRM instances. 

![isochrone illustration](img/isochrone.png)

Compute many *viaroute*
-----------------------
**Retrieve many routes between two QGIS layer of points**:

Request many routes from points in the Origin layer to points in the Destination layer. In the method selection field, select the "Routes between two layers
of points" option. In the "Origin layer" field, select the layer that will be used as origin points. In the "Destination layer" field, select the layer
that will be used as destination points. To save routes as a shape file, click on the *[Browse]* button and select an output location and filename. Click on
the *[Compute and save the result]* button to get the calculations.

Request many routes from a CSV file. In the method selection field, select "Routes from a .csv of paired origins-destinations". Click on the 
*[Browse]* button and choose a CSV file containing origins-destinations coordinates. In "Origin coords" and "Destination" field columns, select latitude
and longitude columns from the CSV file. To view routes on the map, check the "Add the result to the canvas" field. In Click on the *[Compute and save the result]*
button to get the calculations.

![batch routes illustration](img/many_routes.png)

Display the solution of the Travelling Salesman Problem
-------------------------------------------------------
**Display the result of the Travelling Salesman Problem computed by OSRM**:

Request travelling salesman problem computation by selecting "Source point layer". Marking "Display routing instructions" will create an additional
instructions layer that contains an attribute table with routing instructions. Click on the *[Display the result]* button to get the calculations.

![tsp illustration](img/tsp.png)

Found a bug?
===================================
If you found a bug, feel free to report it at https://github.com/strues-maps/qgis_osrm/issues


Commercial support and improvements
===================================

In case you need commercial support for this plugin, feel free to contact current
developer via e-mail at info@strues-maps.lt, subject - qgis osrm plugin.