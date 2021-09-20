"""
This file is used for other modules to access the settings for the application

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
import io
import logging
import sys
import warnings
from typing import Dict, List, Optional, Union

import yaml
from privex.helpers import DictObject, empty, env_bool, env_int, random_str
from privex.loghelper import LogHelper
from yaml import safe_load
from pathlib import Path
from os import getcwd, getenv as env

APP_DIR = Path(__file__).expanduser().resolve().parent
BASE_DIR = APP_DIR.parent
PWD = Path(getcwd()).expanduser().resolve()

try:
    import dotenv
    if hasattr(dotenv, 'load_dotenv'):
        dotenv.load_dotenv(str(BASE_DIR / '.env'))
        dotenv.load_dotenv(str(PWD / '.env'))
        dotenv.load_dotenv()
    elif hasattr(dotenv, 'read_dotenv'):
        dotenv.read_dotenv(str(BASE_DIR / '.env'))
        dotenv.read_dotenv(str(PWD / '.env'))
    else:
        warnings.warn("Unknown dotenv package - neither load_dotenv nor read_dotenv are available. "
                      "Please remove whatever package is currently providing 'dotenv', and then "
                      "install a good dotenv package: 'python3 -m pip install -U python-dotenv'")
except (ImportError, AttributeError, ValueError, OSError) as e:
    pass


CFGTYPE_MAP = DictObject(
    docker='example.dk-config.yaml',
    dk='example.dk-config.yaml',
    compose='example.dk-config.yaml',
    env='example.env',
    environment='example.env',
    dotenv='example.env',
    config='example.yaml',
    yaml='example.yaml',
    yml='example.yaml',
    example='example.yaml',
)
_CONFIG_FILES: List[str] = env('CONFIG_FILES', [
    'config.yaml', 'config.yml', 'ngen.yaml', 'ngen.yml',
    PWD / 'config.yaml', PWD / 'config.yml', PWD / 'ngen.yaml', PWD / 'ngen.yml',
    '~/.neighgen/config.yaml', '~/.neighgen/config.yml'
    '~/.ngen/config.yaml', '~/.ngen/config.yml'
    '~/.ngen.yaml', '~/.ngen.yml'
    '~/.peeringdb/config.yaml', '~/.peeringdb/config.yml'
])

CONFIG_FILES: List[Path] = []

for c in _CONFIG_FILES:
    c = Path(c).expanduser() if c.startswith('/') or c.startswith('~') else BASE_DIR / c
    CONFIG_FILES.append(c.resolve())

CONFIG_FILE: Optional[Path] = None

CONFIG = DictObject(
    orm=DictObject(
        backend='django_peeringdb',
        database=DictObject(
            engine=env('DB_ENGINE', 'postgresql'),
            host=env('DB_HOST', ''),
            name=env('DB_NAME', 'peeringdb'),
            user=env('DB_USER', 'peeringdb'),
            password=env('DB_PASS', env('DB_PASSWORD', '')),
            port=env_int('DB_PORT', 5432),
        ),
        migrate=True,
        secret_key=env('SECRET_KEY', random_str()),
    ),
    sync=DictObject(
        only=[],
        user=env('PDB_USER', ''),
        password=env('PDB_PASS', env('PDB_PASSWORD', '')),
        strip_tz=1,
        timeout=120,
        url='https://www.peeringdb.com/api'
    ),
    app=DictObject(
        log_level=env('LOG_LEVEL', ''),
        debug=env_bool('DEBUG', False),
        template_map=DictObject(
            ios='neigh_ios.j2',
            nxos='neigh_nxos.j2',
        ),
        max_prefixes=DictObject(
            v4=10000,
            v6=10000,
            threshold=90,
            use=True,
            action='restart',
            interval=30,
            config='{threshold} {action} {interval}'
        ),
        cache=DictObject(
            adapter=env('CACHE_ADAPTER', 'sqlite'),
            host=env('CACHE_HOST', None),
            port=env_int('CACHE_PORT', None),
            db=env_int('CACHE_DBNUM', None),
        ),
        default_os='nxos',
        peer_template='PEER',
        peer_policy_v4='PEER-V4',
        peer_policy_v6='PEER-V6',
        peer_session='EBGP',
        lock_version=True,
        ix_trim=False,
        ix_trim_words=1,
    ),
)

for c in CONFIG_FILES:
    if not c.exists(): continue
    CONFIG_FILE = c
    with open(c, 'r') as fh:
        nconf = DictObject(safe_load(fh))
    if 'orm' in nconf:
        nconf.orm = DictObject(nconf.orm)
        if 'database' in nconf.orm:
            nconf.orm.database = DictObject(nconf.orm.database)
            CONFIG.orm.database = DictObject({**CONFIG.orm.database, **nconf.orm.database})
            del nconf.orm['database']
        CONFIG.orm = DictObject({**CONFIG.orm, **nconf.orm})
        del nconf['orm']
    if 'sync' in nconf:
        nconf.sync = DictObject(nconf.sync)
        CONFIG.sync = DictObject({**CONFIG.sync, **nconf.sync})
        del nconf['sync']
    if 'app' in nconf:
        nconf.app = DictObject(nconf.app)
        CONFIG.app = DictObject({**CONFIG.app, **nconf.app})
        del nconf['app']

    CONFIG = DictObject({**CONFIG, **nconf})
    break

config = CONFIG
config.debug, config.log_level = config.app.debug, config.app.log_level
max_prefixes = config.max_prefixes = config.app.max_prefixes

# max_prefixes.config = f'{max_prefixes.threshold} {max_prefixes.action} {max_prefixes.interval}'

DEBUG = config.app.debug
appcfg = config.app
appcfg.log_level = config.log_level = ('DEBUG' if DEBUG else 'WARNING') if empty(config.log_level) else config.log_level
config.cache = appcfg.cache
cachecfg: Union[Dict[str, Union[str, int]], DictObject] = appcfg.cache
LOG_LEVEL = logging.getLevelName(config.log_level.upper())

_lh = LogHelper('ngen', handler_level=LOG_LEVEL)
_lh.add_console_handler(stream=sys.stderr)

PDB_CONFIG = DictObject(orm=config.orm, sync=config.sync)
cfg_outside_keys = ['debug', 'log_level', 'max_prefixes', 'cache']
"""
These are names of convenience keys on :attr:`.CONFIG` - keys which are really just a pointer to another
object nested further in the config, which should be removed before dumping the config to avoid duplication/confusion.
"""

def simplify_dict(ob) -> dict:
    xcfg = dict(ob)
    
    for k, v in ob.items():
        if isinstance(v, DictObject):
            xcfg[k] = dict(v)
            for zk, zv in v.items():
                if isinstance(zv, DictObject):
                    xcfg[k][zk] = dict(zv)
        if isinstance(v, list):
            for zk, zv in enumerate(v):
                if isinstance(zv, DictObject):
                    xcfg[v][zk] = dict(zv)
    return xcfg


def dump_config() -> str:
    xcfg = simplify_dict(config)
    for k in cfg_outside_keys:
        if k in xcfg: del xcfg[k]
    store = io.StringIO()
    d = yaml.dump(xcfg, store)
    return store.getvalue()

# def dump_config(output: Union[str, Path] = None):
#     fh = None
#     try:
#         fh = open(Path(output).expanduser().resolve(), 'w') if output else sys.stdout
#         xcfg = simplify_dict(config)
#         for k in cfg_outside_keys:
#             if k in xcfg: del xcfg[k]
#
#         d = yaml.dump(xcfg, fh)
#         return d
#     finally:
#         if output and fh is not None:
#             fh.close()
