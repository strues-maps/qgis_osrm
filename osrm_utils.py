# -*- coding: utf-8 -*-
"""
/***************************************************************************
 osrm_utils
                                 A QGIS plugin
 Utilities function used for the plugin
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
import csv
import os
from configparser import ConfigParser
from urllib.request import urlopen
from urllib.error import URLError, HTTPError, ContentTooShortError
from functools import lru_cache
import json
import yaml
import numpy as np
from PyQt5.QtGui import QColor
from PyQt5.QtCore import QSettings, QFileInfo
from PyQt5.QtWidgets import QFileDialog, QDialog
from qgis.core import (  # pylint: disable = no-name-in-module
    QgsGeometry, QgsPointXY, QgsCoordinateReferenceSystem,
    QgsProject, QgsCoordinateTransform, QgsSymbol, Qgis,
    QgsCoordinateTransformContext, QgsPoint
)
from qgis.gui import (  # pylint: disable = no-name-in-module
    QgsEncodingFileDialog
)
from matplotlib import use as matplotlib_use
from matplotlib.pyplot import contourf
from scipy.interpolate import griddata
from .osrm_utils_polylline_codec import PolylineCodec

__all__ = ['save_dialog', 'save_dialog_geo', 'prep_access',
           'qgsgeom_from_mpl_collec', 'prepare_route_symbol',
           'encode_to_polyline', 'interpolate_from_times', 'get_coords_ids',
           'pts_ref', "put_on_top", 'decode_geom', 'fetch_table',
           'decode_geom_to_pts', 'fetch_nearest',
           'make_regular_points', 'get_search_frame', 'get_isochrones_colors',
           'read_providers_config', 'save_last_provider', 'load_last_provider']


matplotlib_use('agg')


def _chain(*lists):
    """Flatten array"""
    for li in lists:
        for elem in li:
            yield elem


def encode_to_polyline(pts):
    """Convert point array to encoded polyline"""
    output = []

    def write_enc(coord):
        coord = int(round(coord * 1e5))
        coord <<= 1
        coord = coord if coord >= 0 else ~coord
        while coord >= 0x20:
            output.append((0x20 | (coord & 0x1f)) + 63)
            coord >>= 5
        output.append(coord + 63)

    if len(pts) > 0 and len(pts[0]) > 1:
        write_enc(pts[0][0])
        write_enc(pts[0][1])
        for i, pt in enumerate(pts[1:]):
            write_enc(pt[0] - pts[i][0])
            write_enc(pt[1] - pts[i][1])
        return ''.join([chr(i) for i in output])

    return ''


def prep_access(time_param):
    """Make the regular grid of points, snap them and compute tables"""
    point = time_param['point']
    max_time = time_param['max']
    levels = time_param["levels"]
    url = time_param["url"]
    api_key = time_param["api_key"]

    bounds = get_search_frame(point, max_time)
    coords_grid = make_regular_points(bounds, time_param["max_points"])

    table_data = fetch_table(url, api_key, [point], coords_grid)
    times = table_data[0]
    snapped_dest_coords = table_data[2]

    times = (times[0] / 60.0).round(2)  # Round values in minutes

    # Fetch MatPlotLib polygons from a griddata interpolation
    collec_poly = interpolate_from_times(
        times, np.array(snapped_dest_coords), levels)

    # Convert MatPlotLib polygons to QgsGeometry polygons :
    polygons = qgsgeom_from_mpl_collec(collec_poly.collections)

    return polygons


def save_dialog(filtering="CSV (*.csv *.CSV)"):
    """Dialog for selecting csv file location"""
    settings = QSettings()
    dir_name = settings.value("/UI/lastShapefileDir")
    encode = settings.value("/UI/encoding")
    file_dialog = QgsEncodingFileDialog(
        None, "Save output csv", dir_name, filtering, encode
        )
    file_dialog.setDefaultSuffix('csv')
    file_dialog.setFileMode(QFileDialog.AnyFile)
    file_dialog.setAcceptMode(QFileDialog.AcceptSave)
    if not file_dialog.exec_() == QDialog.Accepted:
        return None, None
    files = file_dialog.selectedFiles()
    settings.setValue(
        "/UI/lastShapefileDir",
        QFileInfo(files[0]).absolutePath()
    )
    return (files[0], file_dialog.encoding())


def open_dialog(filtering="CSV (*.csv *.CSV)"):
    """Dialog for selecting csv file location"""
    settings = QSettings()
    dir_name = settings.value("/UI/lastCsvFileDir")
    encode = settings.value("/UI/encoding")
    encode = 'utf-8' if encode == 'System' else encode

    file_dialog = QgsEncodingFileDialog(
        None, "Choose input csv", dir_name, filtering, encode
        )
    file_dialog.setDefaultSuffix('csv')
    file_dialog.setFileMode(QFileDialog.AnyFile)
    file_dialog.setAcceptMode(QFileDialog.AcceptOpen)
    if not file_dialog.exec_() == QDialog.Accepted:
        return None, None
    files = file_dialog.selectedFiles()
    settings.setValue(
        "/UI/lastCsvFileDir",
        QFileInfo(files[0]).absolutePath()
    )
    return (files[0], file_dialog.encoding())


def read_csv(filename, file_encoding):
    """Read entier csv as list of dictionaries"""
    with open(filename, newline='', encoding=file_encoding) as csvfile:
        reader = csv.DictReader(csvfile)
        data = []
        for row in reader:
            data.append(row)

        return data


def save_dialog_geo(filtering="ESRI Shapefile (*.shp *.SHP)"):
    """Dialog for selecting shp file location"""
    settings = QSettings()
    dir_name = settings.value("/UI/lastShapefileDir")
    encode = settings.value("/UI/encoding")
    file_dialog = QgsEncodingFileDialog(
        None,
        "Save output ShapeFile",
        dir_name,
        filtering,
        encode
    )
    file_dialog.setDefaultSuffix('shp')
    file_dialog.setFileMode(QFileDialog.AnyFile)
    file_dialog.setAcceptMode(QFileDialog.AcceptSave)
    if not file_dialog.exec_() == QDialog.Accepted:
        return None, None
    files = file_dialog.selectedFiles()
    settings.setValue(
        "/UI/lastShapefileDir",
        QFileInfo(files[0]).absolutePath()
    )
    return (files[0], file_dialog.encoding())


def prepare_route_symbol(nb_route):
    """Build route symbols for rendering routes"""
    colors = ['#1f78b4', '#ffff01', '#ff7f00',
              '#fb9a99', '#b2df8a', '#e31a1c']
    p = nb_route % len(colors)
    my_symb = QgsSymbol.defaultSymbol(Qgis.GeometryType.Line)
    my_symb.setColor(QColor(colors[p]))
    my_symb.setWidth(1.2)
    return my_symb


def qgsgeom_from_mpl_collec(collections):
    """Convert MatPlotLib polygons to QgsGeometry polygons"""
    polygons = []
    for path_collection in collections:
        mpoly = []
        for path in path_collection.get_paths():
            path.should_simplify = False
            poly = path.to_polygons()
            if len(poly) > 0 and len(poly[0]) > 3:
                exterior = [QgsPointXY(*p.tolist()) for p in poly[0]]
                holes = [[QgsPointXY(*p.tolist()) for p in h]
                         for h in poly[1:] if len(h) > 3]
                if len(holes) >= 1:
                    mpoly.append([exterior, holes[0]])
                elif len(holes) > 1:
                    mpoly.append([exterior] + [holes])
                else:
                    mpoly.append([exterior])
        if len(mpoly) == 1:
            polygons.append(QgsGeometry.fromPolygonXY(mpoly[0]))
        elif len(mpoly) > 1:
            polygons.append(QgsGeometry.fromMultiPolygonXY(mpoly))
        else:
            polygons.append(QgsGeometry.fromPolygonXY([]))
    return polygons


def interpolate_from_times(times, coords, levels, rev_coords=False):
    """Interpolate polygons from route times and coordinates"""
    if not rev_coords:
        x = coords[..., 0]
        y = coords[..., 1]
    else:
        x = coords[..., 1]
        y = coords[..., 0]
    xi = np.linspace(np.nanmin(x), np.nanmax(x), 200)
    yi = np.linspace(np.nanmin(y), np.nanmax(y), 200)
    x_grid, y_grid = np.meshgrid(xi, yi)

    zi = griddata(coords, times, (x_grid, y_grid), method='linear')
    v_bnd = np.nanmax(abs(zi))
    collec_poly = contourf(xi, yi, zi, levels, vmax=v_bnd, vmin=-v_bnd)

    return collec_poly


def get_coords_ids(layer, field, on_selected=False):
    """Return list of feature geometry and feature id field from layer"""
    if on_selected:
        get_features_method = layer.selectedFeatures
    else:
        get_features_method = layer.getFeatures

    if '4326' not in layer.crs().authid():
        xform = QgsCoordinateTransform(
            layer.crs(),
            QgsCoordinateReferenceSystem.fromEpsgId(4326),
            QgsCoordinateTransformContext()
        )
        coords = [
            xform.transform(ft.geometry().asPoint())
            for ft in get_features_method()
        ]
    else:
        coords = [ft.geometry().asPoint() for ft in get_features_method()]

    if field != '':
        ids = [ft.attribute(field) for ft in get_features_method()]
    else:
        ids = [ft.id() for ft in get_features_method()]

    return coords, ids


def pts_ref(features):
    """Retrieve third item from each feature"""
    return [i[3] for i in features]


def put_on_top(id_new_layer_top, id_old_layer_top):
    """Move layers on top in parent layers"""
    root = QgsProject.instance().layerTreeRoot()

    my_b_layer = root.findLayer(id_new_layer_top)
    my_clone = my_b_layer.clone()
    parent = my_b_layer.parent()
    parent.insertChildNode(0, my_clone)
    parent.removeChildNode(my_b_layer)

    my_a_layer = root.findLayer(id_old_layer_top)
    my_clone = my_a_layer.clone()
    parent = my_a_layer.parent()
    parent.insertChildNode(1, my_clone)
    parent.removeChildNode(my_a_layer)


def decode_geom(encoded_polyline):
    """
    Function decoding an encoded polyline (with 'encoded polyline
    algorithme') and returning a QgsGeometry object

    Params:

    encoded_polyline: str
        The encoded string to decode
    """
    return QgsGeometry.fromPolyline(
        [
            QgsPoint(i[1], i[0])
            for i in PolylineCodec().decode(encoded_polyline)
        ]
    )


def fetch_table(url, api_key, coords_src, coords_dest, metrics='Durations'):
    """
    Function wrapping OSRM 'table' function in order to get a matrix of
    time distance as a numpy array

    Params :
        - url, str: the start of the url to use
            (containing the host and the profile version/name)

        - coords_src, list: a python list of (x, y) coordinates to use
            (they will be used a "sources" if destinations coordinates are
             provided, otherwise they will be used as source and destination
             in order to build a "square"/"symetrical" matrix)

        - coords_dest, list or None: a python list of (x, y) coordinates to use
            (if set to None, only the sources coordinates will be used in order
            to build a "square"/"symetrical" matrix)

    Output:
        - a numpy array containing the time in tenth of seconds
            (where 2147483647 means not-found route)

        - a list of "snapped" source coordinates

        - a list of "snapped" destination coordinates
            (or None if no destination coordinates where provided)
    """
    metrics = metrics.lower()
    if not coords_dest:
        query = ''.join(
            [
                url,
                "polyline(",
                encode_to_polyline([(c[1], c[0]) for c in coords_src]),
                ")?"
                'annotations=',
                metrics[:-1]
            ]
        )
        if api_key:
            query = ''.join([query, 'api_key=', api_key])
    else:
        src_end = len(coords_src)
        dest_end = src_end + len(coords_dest)
        polyline = encode_to_polyline(
            [
                (c[1], c[0]) for c in _chain(coords_src, coords_dest)
            ]
        )
        query = ''.join([
            url,
            "polyline(",
            polyline,
            ")",
            '?sources=',
            ';'.join([str(i) for i in range(src_end)]),
            '&destinations=',
            ';'.join([str(j) for j in range(src_end, dest_end)]),
            '&annotations=',
            metrics[:-1]
        ])
        if api_key:
            query = ''.join([query, '&api_key=', api_key])

    print(f"Fetch table query: {query}")

    try:
        with urlopen(query) as res:
            content = res.read()
            print(content)
            parsed_json = json.loads(content, strict=False)
            assert parsed_json["code"] == "Ok"
            assert metrics in parsed_json
    except AssertionError as er:
        raise ValueError(
            f"Error while contacting OSRM instance : \n{er}"
        ) from er
    except Exception as err:
        raise ValueError(
            f"Error while contacting OSRM instance : \n{err}"
        ) from err

    durations = np.array(parsed_json[metrics], dtype=float)
    new_src_coords = [ft["location"] for ft in parsed_json["sources"]]

    if coords_dest:
        new_dest_coords = [
            ft["location"] for ft in parsed_json["destinations"]
        ]
    else:
        new_dest_coords = None

    return durations, new_src_coords, new_dest_coords


def decode_geom_to_pts(encoded_polyline):
    """
    Params:

    encoded_polyline: str
        The encoded string to decode
    """
    return [(i[1], i[0]) for i in PolylineCodec().decode(encoded_polyline)]


@lru_cache(maxsize=25)
def fetch_nearest(host, profile, coord):
    """
    Useless function wrapping OSRM 'locate' function,
    returning the reponse in JSON.
    More useless since newer version of OSRM doesn't include 'locate' function
    anymore.

    Parameters
    ----------
    coord: list/tuple of two floats
        (x ,y) where x is longitude and y is latitude
    host: str, like 'localhost:5000'
        Url and port of the OSRM instance (no final bakslash)

    Return
    ------
       The coordinates returned by OSRM (or False if any error is encountered)
    """
    url = ''.join(['http://', host, '/nearest/',
                   profile, '/', str(coord[0]), ',', str(coord[1])])
    try:  # Querying the OSRM instance
        with urlopen(url) as rep:
            parsed_json = json.loads(rep.read(), strict=False)
    except (URLError, HTTPError, ContentTooShortError):
        return False
    if 'code' not in parsed_json or "Ok" not in parsed_json['code']:
        return False

    return parsed_json["waypoints"][0]["location"]


def make_regular_points(bounds, nb_pts):
    """
    Return a square grid of regular points (same number in height and width
    even if the bbox is not a square).
    """
    xmin, ymin, xmax, ymax = bounds
    nb_h = int(round(np.sqrt(nb_pts)))
    prog_x = [xmin + i * ((xmax - xmin) / nb_h) for i in range(nb_h + 1)]
    prog_y = [ymin + i * ((ymax - ymin) / nb_h) for i in range(nb_h + 1)]
    result = []
    for x in prog_x:
        for y in prog_y:
            result.append((x, y))
    return result


def get_search_frame(point, max_time):
    """
    Define the search frame (ie. the bbox), given a center point and
    the maximum time requested

    Return
    ------
    xmin, ymin, xmax, ymax : float
    """
    search_len = (max_time * 4) * 1000
    xform = QgsCoordinateTransform(
        QgsCoordinateReferenceSystem.fromEpsgId(4326),
        QgsCoordinateReferenceSystem.fromEpsgId(3857),
        QgsCoordinateTransformContext()
    )
    point = xform.transform(QgsPointXY(*point))
    xmin = point[0] - search_len
    ymin = point[1] - search_len
    xmax = point[0] + search_len
    ymax = point[1] + search_len
    xform = QgsCoordinateTransform(
        QgsCoordinateReferenceSystem.fromEpsgId(3857),
        QgsCoordinateReferenceSystem.fromEpsgId(4326),
        QgsCoordinateTransformContext()
    )
    xmin, ymin = xform.transform(QgsPointXY(xmin, ymin))
    xmax, ymax = xform.transform(QgsPointXY(xmax, ymax))
    return xmin, ymin, xmax, ymax


def get_isochrones_colors(nb_features):
    """ Ugly "helper" function to rewrite to avoid repetitions """
    return {1: ('#a6d96a',),
            2: ('#fee08b', '#a6d96a'),
            3: ('#66bd63',
                '#fee08b', '#f46d43'),
            4: ('#1a9850', '#a6d96a',
                '#fee08b', '#f46d43'),
            5: ('#1a9850', '#66bd63',
                '#ffffbf', '#fc8d59', '#d73027'),
            6: ('#1a9850', '#66bd63', '#d9ef8b',
                '#fee08b', '#fc8d59', '#d73027'),
            7: ('#1a9850', '#66bd63', '#d9ef8b', '#ffffbf',
                '#fee08b', '#fc8d59', '#d73027'),
            8: ('#1a9850', '#66bd63', '#a6d96a', '#d9ef8b',
                '#fee08b', '#fdae61', '#f46d43', '#d73027'),
            9: ('#1a9850', '#66bd63', '#a6d96a', '#d9ef8b', '#ffffbf',
                '#fee08b', '#fdae61', '#f46d43', '#d73027'),
            10: ('#006837', '#1a9850', '#66bd63', '#a6d96a', '#d9ef8b',
                 '#fee08b', '#fdae61', '#f46d43', '#d73027', '#a50026'),
            11: ('#006837', '#1a9850', '#66bd63', '#a6d96a', '#d9ef8b',
                 '#ffffbf', '#fee08b', '#fdae61', '#f46d43', '#d73027',
                 '#a50026'),
            12: ('#006837', '#1a9850', '#66bd63', '#a6d96a', '#d9ef8b',
                 '#e7ef88', '#ffffbf', '#fee08b', '#fdae61', '#f46d43',
                 '#d73027', '#a50026'),
            13: ('#006837', '#1a9850', '#66bd63', '#a6d96a', '#d9ef8b',
                 '#e7ef88', '#ffffbf', '#fee08b', '#fdae61', '#f46d43',
                 '#d73027', '#bb2921', '#a50026'),
            14: ('#006837', '#1a9850', '#66bd63', '#a6d96a', '#d9ef8b',
                 '#e7ef88', '#ffffbf', '#fff6a0', '#fee08b', '#fdae61',
                 '#f46d43', '#d73027', '#bb2921', '#a50026'),
            15: ('#006837', '#1a9850', '#66bd63', '#a6d96a', '#d9ef8b',
                 '#e7ef88', '#ffffbf', '#ffffbf', '#fff6a0', '#fee08b',
                 '#fdae61', '#f46d43', '#d73027', '#bb2921', '#a50026'),
            16: ('#006837', '#1a9850', '#66bd63', '#a6d96a',
                 '#d9ef8b', '#e7ef88', '#ffffbf', '#ffffbf', '#ffffbf',
                 '#fff6a0', '#fee08b', '#fdae61', '#f46d43', '#d73027',
                 '#bb2921', '#a50026'),
            }[nb_features]


def read_providers_config():
    """Read OSRM providers configuration from file"""
    providers_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'providers.yml'
    )

    try:
        with open(providers_file, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            assert "providers" in cfg
            assert isinstance(cfg["providers"], list)
            for provider in cfg["providers"]:
                assert isinstance(provider, dict)
                assert "name" in provider
                assert "base_url" in provider
                assert "api_key" in provider

            return cfg["providers"]
    except (AssertionError, ValueError) as err:
        with open(providers_file, 'w', encoding="utf-8") as fp:
            fp.write("")
            fp.close()
        raise err


def write_providers_config(providers):
    """Write OSRM providers configuration to file"""
    providers_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'providers.yml'
    )
    with open(providers_file, 'w', encoding="utf-8") as fp:
        yaml.dump({"providers": providers}, fp, default_flow_style=False)


def save_last_provider(name):
    """Save last used provider"""
    config_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'config.ini'
    )
    config = ConfigParser()
    config.read(config_file, encoding="utf-8")

    if not config.has_section('provider'):
        config.add_section('provider')

    config.set('provider', 'last_provider', name)

    with open(config_file, 'w', encoding="utf-8") as fp:
        config.write(fp)


def load_last_provider():
    """Load last used provider"""
    config_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'config.ini'
    )
    config = ConfigParser()
    config.read(config_file)
    return config.get('provider', 'last_provider')
