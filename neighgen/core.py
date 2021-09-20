"""
This file is used for initialisation of things such as caching, templating, etc.,
and may also hold general shared functions/methods.

Privex's BGP Neighbour Generator - https://github.com/Privex/neighgen

X11 / MIT License

**Copyright**::

    +===================================================+
    |                 © 2021 Privex Inc.                |
    |               https://www.privex.io               |
    +===================================================+
    |                                                   |
    |        NeighGen                                   |
    |        License: X11/MIT                           |
    |                                                   |
    |        Core Developer(s):                         |
    |                                                   |
    |          (+)  Chris (@someguy123) [Privex]        |
    |          (+)  Kale (@kryogenic) [Privex]          |
    |                                                   |
    +===================================================+
    
    NeighGen - A BGP neighbour config generator written in Python, using PeeringDB's API to discover ASN BGP addresses.
    Copyright (c) 2021    Privex Inc. ( https://www.privex.io )

"""

import hashlib
from typing import Any, Union

from privex.helpers import CacheAdapter, byteify, empty_if

from neighgen import settings
from jinja2 import Environment, PackageLoader, Template, select_autoescape
from privex.helpers.cache import adapter_set, adapter_get
from privex.helpers import settings as pv_settings


def setup_cache(adp: Union[str, CacheAdapter] = None, **kwargs) -> CacheAdapter:
    cf = settings.cachecfg
    adp = empty_if(adp, cf.adapter.lower())
    xadp = None
    if isinstance(adp, str):
        if adp == 'redis':
            from privex.helpers.plugin import configure_redis
            configure_redis(
                **{**dict(
                    host=empty_if(cf.host, pv_settings.REDIS_HOST, zero=True),
                    port=empty_if(cf.port, pv_settings.REDIS_PORT, zero=True),
                    db=empty_if(cf.db, pv_settings.REDIS_DB)
                ), **kwargs}
            )
            xadp = adapter_set('redis')
        elif adp in ['memcache', 'mcache', 'memcached']:
            from privex.helpers.plugin import configure_memcached
            configure_memcached(
                **{**dict(
                    host=empty_if(cf.host, pv_settings.MEMCACHED_HOST, zero=True),
                    port=empty_if(cf.port, pv_settings.MEMCACHED_PORT, zero=True),
                ), **kwargs}
            )
            xadp = adapter_set('memcached')

    return adapter_set(adp) if not xadp else xadp


jinjenv = Environment(
    loader=PackageLoader('neighgen', 'templates'),
    autoescape=select_autoescape(['html', 'xml'])
)


def get_os_template(os: str = 'ios') -> Template:
    if os.endswith('.j2') or os.endswith('.html') or os.endswith('.htm'):
        tp_file = os
    else:
        tp_file: str = settings.config.app.template_map[os]
    tpl: Template = jinjenv.get_template(tp_file)
    return tpl


def md5(o: Union[str, bytes, int, dict, Any]) -> str:
    return hashlib.md5(byteify(str(o) if not isinstance(o, (str, bytes)) else o)).hexdigest()


xcache: CacheAdapter = setup_cache()

