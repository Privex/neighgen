#!/usr/bin/env python3
"""

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
    
    Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation
    files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy,
    modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:
    
    The above copyright notice and this permission notice shall be included in all copies or substantial portions of
    the Software.
    
    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
    WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
    OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
    OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
    
    Except as contained in this notice, the name(s) of the above copyright holders shall not be used in advertising or
    otherwise to promote the sale, use or other dealings in this Software without prior written authorization.
    


"""

import warnings

from setuptools import setup, find_packages
from os.path import join, dirname, abspath
# from privex.helpers.setuppy.common import extras_require
from neighgen.version import VERSION

BASE_DIR = dirname(abspath(__file__))

with open(join(BASE_DIR, "README.md"), "r") as fh:
    long_description = fh.read()


extra_commands = {}

try:
    # noinspection PyUnresolvedReferences
    import privex.helpers.setuppy.commands
    from privex.helpers import settings

    # The file which contains "VERSION = '1.2.3'"
    settings.VERSION_FILE = join(BASE_DIR, 'neighgen', 'version.py')
    
    extra_commands['extras'] = privex.helpers.setuppy.commands.ExtrasCommand
    extra_commands['bump'] = privex.helpers.setuppy.commands.BumpCommand
except (ImportError, AttributeError) as e:
    warnings.warn('Failed to import privex.helpers.setuppy.commands - the commands "extras" and "bump" may not work.')
    warnings.warn(f'Error Reason: {type(e)} - {str(e)}')


setup(
    name='privex_neighgen',

    version=VERSION,

    description="NeighGen - A BGP neighbour config generator written in Python, using PeeringDB's API to discover ASN BGP addresses",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Privex/neighgen",
    author='Chris (Someguy123) @ Privex',
    author_email='chris@privex.io',

    license='MIT',
    install_requires=[
        'privex-helpers[setuppy]>=3.0', 'privex-loghelper', 'privex-db', 'peeringdb>=1.2.1', 'Django',
        'django-peeringdb>=2.9', 'psycopg2', 'PyYAML', 'jinja2', 'rich', 'dicttoxml', 'python-dotenv'
    ],
    cmdclass=extra_commands,
    # extras_require=extras_require(extensions),
    packages=find_packages(exclude=['tests', 'tests.*', 'test.*', 'privex.db', 'privex.db.*']),
    scripts=['bin/neighgen'],
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
