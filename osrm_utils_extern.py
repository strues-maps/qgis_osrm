# -*- coding: utf-8 -*-
"""
osrm_utils_extern
----------
Extern utility functions used for the plugin, for which i'm not the author :

 - lru_cache functionnality, written by Raymond Hettinger (MIT licence, 2012)
 - PolylineCodec class, written by Bruno M. Custodio (MIT licence, 2014)
"""
from functools import update_wrapper
from threading import RLock
from collections import namedtuple

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


###############################################################################
#    Full featured backport from functools.lru_cache for python 2.7.
#
#    Verbatim copy of the recipe published by :
#            Raymond Hettinger (MIT licence, 2012)
#    on ActiveState : http://code.activestate.com/recipes/578078/
###############################################################################

_CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])


class _HashedSeq(list):
    __slots__ = ('hashvalue',)

    def __init__(self, tup, hash_param=hash):
        self[:] = tup
        self.hashvalue = hash_param(tup)

    def __hash__(self):
        return self.hashvalue


def _make_key(args, kwds, typed,
              kwd_mark=(object(),),
              fasttypes=None,
              sorted_param=sorted, tuple_param=tuple,
              type_param=type, len_param=len):
    'Make a cache key from optionally typed positional and keyword arguments'
    if fasttypes is None:
        fasttypes = {int, str, frozenset, type(None)}

    key = args
    if kwds:
        sorted_items = sorted_param(kwds.items())
        key += kwd_mark
        for item in sorted_items:
            key += item
    if typed:
        key += tuple_param(type_param(v) for v in args)
        if kwds:
            key += tuple_param(type_param(v) for k, v in sorted_items)
    elif len_param(key) == 1 and type_param(key[0]) in fasttypes:
        return key[0]
    return _HashedSeq(key)


def lru_cache(maxsize=100, typed=False):
    """Least-recently-used cache decorator.

    If *maxsize* is set to None, the LRU features are disabled and the cache
    can grow without bound.

    If *typed* is True, arguments of different types will be cached separately.
    For example, f(3.0) and f(3) will be treated as distinct calls with
    distinct results.

    Arguments to the cached function must be hashable.

    View the cache statistics named tuple (hits, misses, maxsize, currsize)
    with f.cache_info().  Clear the cache and statistics with f.cache_clear().
    Access the underlying function with f.__wrapped__.

    See:  http://en.wikipedia.org/wiki/Cache_algorithms#Least_Recently_Used

    """

    # Users should only access the lru_cache through its public API:
    #       cache_info, cache_clear, and f.__wrapped__
    # The internals of the lru_cache are encapsulated for thread safety and
    # to allow the implementation to change (including a possible C version).

    def decorating_function(user_function):

        cache = {}
        stats = [0, 0]              # make statistics updateable non-locally
        hits, misses = 0, 1         # names for the stats fields
        make_key = _make_key
        cache_get = cache.get    # bound method to lookup key or return None
        _len = len               # localize the global len() function
        lock = RLock()           # because linkedlist updates aren't threadsafe
        root = []                # root of the circular doubly linked list
        root[:] = [root, root, None, None]    # initialize by pointing to self
        nonlocal_root = [root]                # make updateable non-locally
        prev_idx, next_idx = 0, 1             # names for the link fields

        if maxsize == 0:

            def wrapper(*args, **kwds):
                # no caching, just do a statistics update
                # after a successful call
                result = user_function(*args, **kwds)
                stats[misses] += 1
                return result

        elif maxsize is None:

            def wrapper(*args, **kwds):
                # simple caching without ordering or size limit
                key = make_key(args, kwds, typed)
                # root used here as a unique not-found sentinel
                result = cache_get(key, root)
                if result is not root:
                    stats[hits] += 1
                    return result
                result = user_function(*args, **kwds)
                cache[key] = result
                stats[misses] += 1
                return result

        else:

            def wrapper(*args, **kwds):
                # size limited caching that tracks accesses by recency
                key = make_key(args, kwds, typed) if kwds or typed else args
                with lock:
                    link = cache_get(key)
                    if link is not None:
                        # record recent use of the key by moving it
                        # to the front of the list
                        root, = nonlocal_root
                        link_prev, link_next, key, result = link
                        link_prev[next_idx] = link_next
                        link_next[prev_idx] = link_prev
                        last = root[prev_idx]
                        last[next_idx] = root[prev_idx] = link
                        link[prev_idx] = last
                        link[next_idx] = root
                        stats[hits] += 1
                        return result
                result = user_function(*args, **kwds)
                with lock:
                    root, = nonlocal_root
                    if key in cache:
                        # getting here means that this same key was added to
                        # the cache while the lock was released.  since the
                        # link update is already done, we need only return the
                        # computed result and update the count of misses.
                        pass
                    elif _len(cache) >= maxsize:
                        # use the old root to store the new key and result
                        oldroot = root
                        oldroot[key] = key
                        oldroot[result] = result
                        # empty the oldest link and make it the new root
                        root = nonlocal_root[0] = oldroot[next_idx]
                        oldkey = root[key]
                        root[key] = root[result] = None
                        # now update the cache dictionary for the new links
                        del cache[oldkey]
                        cache[key] = oldroot
                    else:
                        # put result in a new link at the front of the list
                        last = root[prev_idx]
                        link = [last, root, key, result]
                        last[next_idx] = root[prev_idx] = cache[key] = link
                    stats[misses] += 1
                return result

        def cache_info():
            """Report cache statistics"""
            with lock:
                return _CacheInfo(
                    stats[hits], stats[misses], maxsize, len(cache)
                )

        def cache_clear():
            """Clear the cache and cache statistics"""
            with lock:
                cache.clear()
                root = nonlocal_root[0]
                root[:] = [root, root, None, None]
                stats[:] = [0, 0]

        wrapper.__wrapped__ = user_function
        wrapper.cache_info = cache_info
        wrapper.cache_clear = cache_clear
        return update_wrapper(wrapper, user_function)

    return decorating_function

###############################################################################
###############################################################################
