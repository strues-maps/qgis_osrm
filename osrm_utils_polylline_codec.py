# -*- coding: utf-8 -*-
"""
osrm_utils_extern
----------
Extern utility functions used for the plugin, for which i'm not the author :
 - PolylineCodec class, written by Bruno M. Custodio (MIT licence, 2014)
"""

###############################################################################
#
#    Ligthweighted copy of the Polyline Codec for Python
#    (https://pypi.python.org/pypi/polyline)
#    realeased under MIT licence, 2014, by Bruno M. Custodio :
#
###############################################################################


class PolylineCodec:
    """
    Copy of the "_trans" and "decode" functions
    from the Polyline Codec (https://pypi.python.org/pypi/polyline) released
    under MIT licence, 2014, by Bruno M. Custodio.
    """

    def _trans(self, value, index):
        """Decode single byte"""
        byte, result, shift = None, 0, 0
        while (byte is None or byte >= 0x20):
            byte = ord(value[index]) - 63
            index += 1
            result |= (byte & 0x1f) << shift
            shift += 5
            comp = result & 1
        return ~(result >> 1) if comp else (result >> 1), index

    def decode(self, expression):
        """Decode a polyline string into a set of coordinates."""
        coordinates, index, lat, lng, length = [], 0, 0, 0, len(expression)
        while index < length:
            lat_change, index = self._trans(expression, index)
            lng_change, index = self._trans(expression, index)
            lat += lat_change
            lng += lng_change
            coordinates.append((lat / 1e5, lng / 1e5))
        return coordinates
