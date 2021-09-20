"""
This is the main module, containing all the important code that powers the application.

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
import argparse
import json
import sys
import textwrap
from copy import copy, deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Any, Generator, Iterable, List, Optional, Type, Union
from xml.dom import minidom

import yaml
from jinja2 import Template
from peeringdb import resource
from peeringdb.client import Client
from privex.helpers import DictDataClass, DictObject, ErrHelpParser, empty, empty_if, T, r_cache, stringify
from dataclasses import dataclass, field

from rich import box
from rich.columns import Columns
from rich.containers import Renderables
from rich.panel import Panel

from neighgen.core import md5
from neighgen import core, settings
from rich.table import Table
from rich.console import Console, Group
from rich.layout import Layout
from dicttoxml import dicttoxml


__all__ = [
    'console_std', 'console_err', 'rprint', 'stdprint', 'printstd', 'print_std', 'errprint', 'printerr', 'print_err',
    'appcfg', 'PDFacility', 'PDExchange', 'PDContact', 'PDNetwork',
    'update_db', 'lookup_asn', '_lookup_asn', 'generate_neigh', 'extract_number', 'cmd_asinfo', 'main', 'run_main'
]

from neighgen.settings import CFGTYPE_MAP

console_std = Console(soft_wrap=True)
console_err = Console(stderr=True)
rprint = stdprint = printstd = print_std = console_std.print
errprint = printerr = print_err = console_err.print
appcfg = settings.appcfg


def purge_parent(o: T) -> T:
    if isinstance(o, PDNetwork):
        for x in o.facilities: x.raw_data, x.parent = {}, None
        for x in o.ixps: x.raw_data, x.parent = {}, None
        for x in o.contacts: x.raw_data, x.parent = {}, None
        o.raw_data = {}
    elif isinstance(o, (list, tuple)):
        return [purge_parent(v) for v in o]
    else:
        if hasattr(o, 'parent'): o.parent = None
        if hasattr(o, 'raw_data'): o.raw_data = {}
        if isinstance(o, dict):
            if 'parent' in o: del o['parent']
            if 'raw_data' in o: del o['raw_data']
            if 'poc_set' in o: o['poc_set'] = purge_parent(o['poc_set'])
            if 'netixlan_set' in o: o['netixlan_set'] = purge_parent(o['netixlan_set'])
            if 'netfac_set' in o: o['netfac_set'] = purge_parent(o['netfac_set'])
    return o


@dataclass
class PDFacility(DictDataClass):
    class DictConfig:
        dict_convert_mode: Optional[str] = "merge_dc"
        dict_listify: List[str] = []
        """
        Keys which contain iterable's (list/set etc.) of objects such as those based on :class:`.DictDataClass` / :class:`.Dictable`,
        which should be converted into a list of :class:`.dict`'s using ``dict()``.

        Example:

            >>> @dataclass
            >>> class Order(DictDataClass):
            ...     hello: str = 'world'
            >>>
            >>> class MyDataclass(DictDataClass):
            ...     class DictConfig:
            ...         dict_listify = ['orders']
            ...     lorem = 'ipsum'
            ...     orders: list = [Order(), Order('test')]
            ...
        """
        dict_exclude_base: List[str] = ['raw_data', 'DictConfig', '_DictConfig']
        dict_exclude: List[str] = ['parent', 'raw_data']
        """
        A list of attributes / raw_data keys to exclude when your instance is converted into a :class:`.dict`
        """
    id: int
    name: str = ''
    city: str = ''
    fac_id: int = None
    local_asn: int = None
    created: str = ''
    updated: str = ''
    status: str = ''
    parent: Optional["PDNetwork"] = None
    raw_data: DictObject = field(default_factory=DictObject, repr=False)
    
    def purge(self) -> "PDFacility": return purge_parent(self)

    def __copy__(self):
        return self.__deepcopy__()

    def __deepcopy__(self, memodict={}) -> "PDFacility":
        cls: Type["PDFacility"] = self.__class__
        return cls(
            id=deepcopy(self.id), fac_id=deepcopy(self.fac_id), name=deepcopy(self.name),
            city=deepcopy(self.city), local_asn=deepcopy(self.local_asn), parent=copy(self.parent),
            created=deepcopy(self.created), updated=deepcopy(self.updated), status=deepcopy(self.status),
        )

    def __iter__(self):
        xparent = self.parent
        newx = self.__deepcopy__()
        newx = newx.purge()
        resnew = []
        for k, v in super(PDFacility, newx).__iter__():
            if k in self._dc_dict_config.dict_exclude: continue
            resnew.append((k, v),)
        resnew.append(('parent', xparent))
        for k, v in resnew:
            yield k, v

@dataclass
class PDExchange(DictDataClass):
    class DictConfig:
        dict_convert_mode: Optional[str] = "merge_dc"
        dict_listify: List[str] = []
        """
        Keys which contain iterable's (list/set etc.) of objects such as those based on :class:`.DictDataClass` / :class:`.Dictable`,
        which should be converted into a list of :class:`.dict`'s using ``dict()``.

        Example:

            >>> @dataclass
            >>> class Order(DictDataClass):
            ...     hello: str = 'world'
            >>>
            >>> class MyDataclass(DictDataClass):
            ...     class DictConfig:
            ...         dict_listify = ['orders']
            ...     lorem = 'ipsum'
            ...     orders: list = [Order(), Order('test')]
            ...
        """
        dict_exclude_base: List[str] = ['raw_data', 'DictConfig', '_DictConfig']
        dict_exclude: List[str] = ['parent', 'raw_data']
        """
        A list of attributes / raw_data keys to exclude when your instance is converted into a :class:`.dict`
        """
    id: int
    ix_id: int = None
    name: str = ''
    ixlan_id: int = None
    note: str = field(default='', repr=False)
    speed: int = 0
    asn: int = None
    ipaddr4: str = ''
    ipaddr6: str = ''
    is_rs_peer: bool = False
    operational: bool = False
    created: str = field(default='', repr=False)
    updated: str = field(default='', repr=False)
    status: str = ''
    parent: Optional["PDNetwork"] = None
    raw_data: DictObject = field(default_factory=DictObject, repr=False)

    def purge(self) -> "PDExchange": return purge_parent(self)

    def __copy__(self):
        return self.__deepcopy__()
    
    def __deepcopy__(self, memodict={}) -> "PDExchange":
        cls: Type["PDExchange"] = self.__class__
        return cls(
            id=deepcopy(self.id), ix_id=deepcopy(self.ix_id), name=deepcopy(self.name),
            speed=deepcopy(self.speed), asn=deepcopy(self.asn), ipaddr4=deepcopy(self.ipaddr4),
            ipaddr6=deepcopy(self.ipaddr6), is_rs_peer=deepcopy(self.is_rs_peer), operational=deepcopy(self.operational),
            created=deepcopy(self.created), updated=deepcopy(self.updated), status=deepcopy(self.status),
            parent=copy(self.parent),
        )

    def __iter__(self):
        xparent = self.parent
        newx = self.__deepcopy__()
        newx = newx.purge()
        resnew = []
        for k, v in super(PDExchange, newx).__iter__():
            if k in self._dc_dict_config.dict_exclude: continue
            resnew.append((k, v), )
        resnew.append(('parent', xparent))
        for k, v in resnew:
            yield k, v

@dataclass
class PDContact(DictDataClass):
    class DictConfig:
        dict_convert_mode: Optional[str] = "merge_dc"
        dict_listify: List[str] = []
        """
        Keys which contain iterable's (list/set etc.) of objects such as those based on :class:`.DictDataClass` / :class:`.Dictable`,
        which should be converted into a list of :class:`.dict`'s using ``dict()``.

        Example:

            >>> @dataclass
            >>> class Order(DictDataClass):
            ...     hello: str = 'world'
            >>>
            >>> class MyDataclass(DictDataClass):
            ...     class DictConfig:
            ...         dict_listify = ['orders']
            ...     lorem = 'ipsum'
            ...     orders: list = [Order(), Order('test')]
            ...
        """
        dict_exclude_base: List[str] = ['raw_data', 'DictConfig', '_DictConfig']
        dict_exclude: List[str] = ['parent', 'raw_data']
        """
        A list of attributes / raw_data keys to exclude when your instance is converted into a :class:`.dict`
        """
    id: int
    role: str = ''
    visible: str = ''
    name: str = ''
    phone: str = ''
    email: str = ''
    url: str = ''
    created: str = field(default='', repr=False)
    updated: str = field(default='', repr=False)
    status: str = ''
    parent: Optional["PDNetwork"] = None
    raw_data: DictObject = field(default_factory=DictObject, repr=False)

    def __copy__(self):
        return self.__deepcopy__()

    def __deepcopy__(self, memodict={}) -> "PDContact":
        cls: Type["PDFacility"] = self.__class__
        return cls(
            id=deepcopy(self.id), role=deepcopy(self.role), name=deepcopy(self.name),
            visible=deepcopy(self.visible), phone=deepcopy(self.phone), parent=copy(self.parent),
            email=deepcopy(self.email), url=deepcopy(self.url),
            created=deepcopy(self.created), updated=deepcopy(self.updated), status=deepcopy(self.status),
        )

    def purge(self) -> "PDContact": return purge_parent(self)

    def __iter__(self):
        xparent = self.parent
        newx = self.__deepcopy__()
        newx = newx.purge()
        resnew = []
        for k, v in super(PDContact, newx).__iter__():
            if k in self._dc_dict_config.dict_exclude: continue
            resnew.append( (k, v), )
        resnew.append( ('parent', xparent) )
        for k, v in resnew:
            yield k, v


@dataclass
class PDNetwork(DictDataClass):
    class DictConfig:
        dict_convert_mode: Optional[str] = "merge_dc"
        dict_listify: List[str] = ['netfac_set', 'netixlan_set', 'poc_set']
        """
        Keys which contain iterable's (list/set etc.) of objects such as those based on :class:`.DictDataClass` / :class:`.Dictable`,
        which should be converted into a list of :class:`.dict`'s using ``dict()``.

        Example:

            >>> @dataclass
            >>> class Order(DictDataClass):
            ...     hello: str = 'world'
            >>>
            >>> class MyDataclass(DictDataClass):
            ...     class DictConfig:
            ...         dict_listify = ['orders']
            ...     lorem = 'ipsum'
            ...     orders: list = [Order(), Order('test')]
            ...
        """
        dict_exclude_base: List[str] = ['raw_data', 'DictConfig', '_DictConfig']
        dict_exclude: List[str] = ['parent', 'raw_data']
        """
        A list of attributes / raw_data keys to exclude when your instance is converted into a :class:`.dict`
        """
    id: int
    name: str = ''
    name_long: str = field(default='', repr=False)
    aka: str = ''
    website: str = ''
    orig_id: int = field(default=None, repr=False)
    asn: int = None
    looking_glass: str = ''
    route_server: str = field(default='', repr=False)
    irr_as_set: str = ''
    info_type: str = field(default='', repr=False)
    info_prefixes4: int = 0
    info_prefixes6: int = 0
    info_traffic: str = field(default='', repr=False)
    info_ratio: str = field(default='', repr=False)
    info_scope: str = field(default='', repr=False)
    info_unicast: bool = field(default=True, repr=False)
    info_multicast: bool = field(default=False, repr=False)
    info_ipv6: bool = False
    info_never_via_route_servers: bool = field(default=False, repr=False)

    ix_count: int = 0
    fac_count: int = 0
    notes: str = field(default='', repr=False)
    netixlan_updated: str = field(default='', repr=False)
    netfac_updated: str = field(default='', repr=False)
    poc_updated: str = field(default='', repr=False)
    policy_url: str = field(default='', repr=False)
    policy_general: str = field(default='', repr=False)
    policy_locations: str = field(default='', repr=False)
    policy_ratio: bool = field(default=False, repr=False)
    policy_contracts: str = field(default='', repr=False)
    
    netfac_set: List[PDFacility] = field(default_factory=list, repr=False)
    netixlan_set: List[PDExchange] = field(default_factory=list, repr=False)
    poc_set: List[PDContact] = field(default_factory=list, repr=False)
    
    allow_ixp_update: bool = field(default=False, repr=False)
    created: str = field(default='', repr=False)
    updated: str = field(default='', repr=False)
    status: str = ''
    raw_data: DictObject = field(default_factory=DictObject, repr=False)

    @property
    def ixps(self) -> List[PDExchange]: return self.netixlan_set

    @property
    def facilities(self) -> List[PDFacility]: return self.netfac_set

    @property
    def contacts(self) -> List[PDContact]: return self.poc_set
    
    def find_ixps(
        self, name: str = None, ix_id: int = None, _id: int = None, exact: bool = False, **kwargs
    ) -> Generator[PDExchange, None, None]:
        kwargs = DictObject(kwargs)
        if 'ipv4' in kwargs: kwargs.ip4 = kwargs.ipv4
        if 'ipaddr4' in kwargs: kwargs.ip4 = kwargs.ipaddr4
        if 'ipv6' in kwargs: kwargs.ip6 = kwargs.ipv6
        if 'ipaddr6' in kwargs: kwargs.ip6 = kwargs.ipaddr6
        
        for x in self.ixps:
            if not empty(name):
                if exact:
                    if x.name.lower() == name.lower(): yield x
                else:
                    if name.lower() in x.name.lower(): yield x
            if not empty(ix_id):
                if x.ix_id == ix_id or x.ixlan_id == ix_id: yield x
            if not empty(_id):
                if x.id == _id: yield x

            if 'ip4' in kwargs and not empty(kwargs.ip4):
                if x.ipaddr4 == kwargs.ip4: yield x
            if 'ip6' in kwargs and not empty(kwargs.ip6):
                if x.ipaddr6 == kwargs.ip6: yield x

    def find_ixp(self, name: str = None, ix_id: int = None, _id: int = None, exact: bool = False, **kwargs) -> Optional[PDExchange]:
        zixps = list(self.find_ixps(name, ix_id=ix_id, _id=_id, exact=exact, **kwargs))
        return None if empty(zixps, itr=True) else zixps[0]

    def __post_init__(self):
        if not empty(self.netfac_set, itr=True) and not isinstance(self.netfac_set[0], int):
            self.netfac_set = [PDFacility.from_dict({**d, "parent": self}) for d in self.netfac_set]
        if not empty(self.netixlan_set, itr=True) and not isinstance(self.netixlan_set[0], int):
            self.netixlan_set = [PDExchange.from_dict({**d, "parent": self}) for d in self.netixlan_set]
        if not empty(self.poc_set, itr=True) and not isinstance(self.poc_set[0], int):
            self.poc_set = [PDContact.from_dict({**d, "parent": self}) for d in self.poc_set]

    def purge(self) -> "PDNetwork": return purge_parent(self)
    
    def __iter__(self):
        exclude = self.DictConfig.dict_exclude_base + self.DictConfig.dict_exclude
        
        dt = {k: v for k, v in self.__dict__.items() if not k.startswith('__') and k not in exclude}
        
        for lkey in self.DictConfig.dict_listify:
            dt[lkey] = [dict(d) for d in dt[lkey]]
        
        for k, v in dt.items():
            yield k, v

    # def __iter__(self):
    #     self.purge()
    #     return super().__iter__()


def update_db(cfg: Optional[dict] = None, **kwargs):
    pdb = Client(cfg)
    return pdb.update_all(**kwargs)


def lookup_asn(asn: Union[int, str], depth=3, cfg: Optional[dict] = None) -> List[PDNetwork]:
    xres: List[dict] = _lookup_asn(asn, depth, cfg)
    res: List[PDNetwork] = list(PDNetwork.from_list(xres))
    return res


@r_cache(lambda asn, depth=3, cfg=None: f"ngen:_lookup_asn:{asn}:{depth}:{md5(cfg)}")
def _lookup_asn(asn: Union[int, str], depth=3, cfg: Optional[dict] = None) -> List[dict]:
    asn = int(asn)
    pdb = Client(cfg)
    # noinspection PyUnresolvedReferences
    xres: List[dict] = pdb.fetch_all(resource.Network, depth, asn=asn)
    return xres


def generate_neigh(
    ix: PDExchange, netwk: PDNetwork = None, peer_idx=1, port='',
    lock_version=appcfg.lock_version, os=appcfg.default_os, **kwargs
) -> str:
    if not netwk and not empty(ix.parent, itr=True, zero=True):
        netwk = ix.parent
    max_prefix_thresh = kwargs.get('max_prefix_thresh', settings.max_prefixes.threshold)
    max_prefix_action = kwargs.get('max_prefix_action', settings.max_prefixes.action)
    max_prefix_interval = kwargs.get('max_prefix_interval', settings.max_prefixes.interval)
    max_prefix_config: str = kwargs.get('max_prefix_config', settings.max_prefixes.config)
    max_prefix_config = max_prefix_config.format(threshold=max_prefix_thresh, action=max_prefix_action, interval=max_prefix_interval)
    ctx = DictObject(
        ipv4_address=ix.ipaddr4,
        ipv6_address=ix.ipaddr6,
        peer_template=kwargs.get('peer_template', appcfg.peer_template),
        peer_policy_v4=kwargs.get('peer_policy_v4', appcfg.peer_policy_v4),
        peer_policy_v6=kwargs.get('peer_policy_v6', appcfg.peer_policy_v6),
        peer_session=kwargs.get('peer_session', appcfg.peer_session),
        asn=netwk.asn if netwk else empty_if(ix.asn, kwargs.get('asn'), zero=True),
        as_name=netwk.name if netwk else kwargs.get('as_name'),
        peer_idx=peer_idx,
        ix_name=ix.name,
        port=port,
        lock_version=lock_version,
        use_max_prefixes=kwargs.get('use_max_prefixes', True),
        max_prefixes_v4=kwargs.get('max_prefixes_v4', empty_if(netwk.info_prefixes4, settings.max_prefixes.v4, zero=True)),
        max_prefixes_v6=kwargs.get('max_prefixes_v6', empty_if(netwk.info_prefixes6, settings.max_prefixes.v6, zero=True)),
        max_prefix_config=max_prefix_config,
    )
    trim_name: bool = kwargs.get('trim_name', appcfg.ix_trim)
    trim_words: int = kwargs.get('trim_words', appcfg.ix_trim_words)
    if trim_name:
        ctx.ix_name = ' '.join(ctx.ix_name.split()[:trim_words])
    tpl: Template = core.get_os_template(os)
    return tpl.render(**ctx)


def extract_number(o, cast: Type[T] = int) -> T:
    o = list(str(o))
    xnum = ''
    for n in o:
        n: str
        if n.isnumeric() or n.isdigit() or n.isdecimal():
            xnum += n
    return cast(xnum) if cast else xnum


def xgrid(
    *rows: Union[Renderables, Iterable[Renderables], Table, Iterable[Table]],
        headers: Iterable[Any] = None, column_kwargs=None, **kwargs) -> Table:
    rows = list(rows)
    column_kwargs = empty_if(column_kwargs, {}, itr=True)
    row_kwargs = kwargs.pop('row_kwargs', {})
    headers = empty_if(headers, [], itr=True)
    firstrow = rows[0]
    tbl = Table.grid(*headers, **kwargs)
    if len(headers) == 0:
        if isinstance(firstrow, (tuple, list)):
            for x in range(len(firstrow)):
                tbl.add_column(**column_kwargs)
        else:
            tbl.add_column(**column_kwargs)
    for rw in rows:
        if not isinstance(rw, (list, tuple)): rw = [rw]
        tbl.add_row(*rw, **row_kwargs)
    
    return tbl


def cmd_asinfo(opt: argparse.Namespace):
    asn = extract_number(opt.asn, int)
    
    list_ixps, list_facs = opt.list_ixps, opt.list_facs
    depth = 3 if any([list_ixps, list_facs]) else 0
    xasn = lookup_asn(asn, depth)[0]
    tb_conf = dict(
        box=box.SQUARE, show_lines=True, padding=(0, 1, 1, 1),
        min_width=50, expand=True
    )
    tbl = Table(
        title=f'{xasn.name} - AS{xasn.asn}', **tb_conf
    )
    tbl.add_column('Key', header_style='bold yellow', style='bold yellow', )
    tbl.add_column('Value', header_style='bold green', style='green')
    tbl.add_row('Name', xasn.name)
    tbl.add_row('AS Number', str(xasn.asn))
    tbl.add_row('Website', str(xasn.website))
    tbl.add_row('AS-SET', str(xasn.irr_as_set))
    tbl.add_row('Content Type', str(xasn.info_type))
    tbl.add_row('Max IPv4 Prefixes', str(xasn.info_prefixes4))
    tbl.add_row('Max IPv6 Prefixes', str(xasn.info_prefixes6))
    tbl.add_row('Traffic Amount', str(xasn.info_traffic))
    tbl.add_row('Traffic Ratio', str(xasn.info_ratio))
    tbl.add_row('Supports IPv6', str(xasn.info_ipv6))
    tbl.add_row('Created At', str(xasn.created))

    peering_tbl = Table(title=f'Peering Info - {xasn.name} - AS{xasn.asn}', **tb_conf)
    peering_tbl.add_column('Key', header_style='bold magenta', style='bold magenta')
    peering_tbl.add_column('Value', header_style='bold cyan', style='cyan')
    peering_tbl.add_row('Number of IXPs present on', str(xasn.ix_count))
    peering_tbl.add_row('Number of Facilities present on', str(xasn.fac_count))
    peering_tbl.add_row('Never uses Route Servers', str(xasn.info_never_via_route_servers))
    peering_tbl.add_row('Peering Policy URL', str(xasn.policy_url))
    peering_tbl.add_row('Peering Policy Type', str(xasn.policy_general))
    peering_tbl.add_row('Peering Policy Locations', str(xasn.policy_locations))
    peering_tbl.add_row('Peering Policy Ratio Required', str(xasn.policy_ratio))
    peering_tbl.add_row('Peering Policy Contract Required', str(xasn.policy_contracts))
    
    notes_table = Table('[bold][green]Notes / Description[/][/bold]', **tb_conf)
    notes_table.add_row(str(xasn.notes), style='cyan')
    
    # gd_peerwrap = Table.grid(expand=True)
    # gd_peerwrap.add_column()
    #
    # gd = Table.grid(expand=True)
    # gd.add_column()
    # gd.add_column()
    
    # gd.add_row(notes_table)
    # lyot = Layout()
    # lyot.split_column(
    #     Layout(name="upper", ratio=3),
    #     Layout(name="lower", ratio=1),
    # )
    # lyot['upper'].split_row(tbl, peering_tbl)
    # lyot['lower'].split(notes_table)
    # print_std(tbl, peering_tbl)
    # print_std(notes_table)
    #
    if len(str(xasn.notes)) < 600:
        # gd.add_row("",  notes_table)
        # gd.add_row(tbl, peering_tbl)
        # gd = xgrid(
        #     [tbl, xgrid(peering_tbl, notes_table, expand=False)], expand=False
        # )
        # gd_peerwrap.add_row(peering_tbl)
        # gd_peerwrap.add_row(notes_table)
        # gd.add_row(tbl, gd_peerwrap)
        # print_std(gd)
        peering_tbl.min_width = 100
        peering_tbl.columns[0].max_width = 50
        peering_tbl.columns[1].max_width = 50
        notes_table.columns[0].max_width = 100
        print_std(Columns(
            [
                tbl,
                xgrid(peering_tbl, notes_table,
                      column_kwargs=dict(min_width=50), expand=True), ],
            equal=False, expand=False
        ))

    else:
        # gd.add_row(tbl, peering_tbl)
        # notes_table.width = 70
        # Panel
        print_std(Columns(
            [tbl, peering_tbl,],
            equal=True, expand=True
        ))
        print_std(notes_table)
        # print_std(xgrid([tbl, peering_tbl], expand=False))
        # print_std(notes_table)

    # else:
    print_std()
    # print_std(notes_table)
    print_std()
    
    combo_info = all([list_ixps, list_facs])
    tbl_facs, tbl_ix = None, None
    
    if list_ixps:
        tbl_ix = Table(
            title=f'{xasn.name} ({xasn.asn}) is present at these IXPs:', padding=(0, 1, 1, 1),
            min_width=30 if combo_info else 250
        )
        tbl_ix.add_column('Exchange', header_style='bold yellow', style='yellow')
        tbl_ix.add_column('Port Speed', header_style='bold green', style='green')
        tbl_ix.add_column('ASN', header_style='bold cyan', style='cyan')
        tbl_ix.add_column('IPv4 Address', header_style='bold green', style='green')
        tbl_ix.add_column('IPv6 Address', header_style='bold magenta', style='magenta')
        tbl_ix.add_column('Route Server Peer', header_style='bold yellow')
        tbl_ix.add_column('Working', header_style='bold yellow')
        
        for zx in xasn.ixps:
            xspeed = f"{zx.speed} mbps"
            zspeed = Decimal(zx.speed)
            if zspeed >= 1000:
                gbspeed = Decimal(zx.speed) / Decimal('1000')
                xspeed = f"{gbspeed:.1f} gbps" if (gbspeed % Decimal('1')) > Decimal('0') else f"{int(gbspeed)} gbps"
            if zspeed < 200: xspeed = f'[red]{xspeed}[/]'
            elif zspeed < 1000: xspeed = f'[yellow]{xspeed}[/]'
            elif zspeed < 3000: xspeed = f'[magenta]{xspeed}[/]'
            elif zspeed < 20000: xspeed = f'[cyan]{xspeed}[/]'
            elif zspeed < 100000: xspeed = f'[bold][cyan]{xspeed}[/][/]'
            elif zspeed < 200000: xspeed = f'[green]{xspeed}[/]'
            else: xspeed = f'[bold][green]{xspeed}[/][/]'
            rs_note = '[bold][green]YES[/][/]' if zx.is_rs_peer else '[bold][red]NO[/][/]'
            oper_note = '[bold][green]YES[/][/]' if zx.operational else '[bold][red]NO[/][/]'
            tbl_ix.add_row(
                zx.name, xspeed, f"{zx.asn}", f"{zx.ipaddr4}", f"{zx.ipaddr6}", rs_note, oper_note
            )
        
        if not combo_info:
            print_std(xgrid(['', '', tbl_ix, ''], padding=(10, 10, 10, 10), column_kwargs=dict(justify='center')))
        print_std()

    if list_facs:
        tbl_facs = Table(title=f'{xasn.name} ({xasn.asn}) is present at these Facilities:', padding=(0, 1, 1, 1),
                         min_width=30 if combo_info else 250)
        tbl_facs.add_column('Facility', header_style='bold yellow', style='yellow')
        tbl_facs.add_column('City/Country', header_style='bold green', style='green')
        tbl_facs.add_column('ASN', header_style='bold cyan', style='cyan')
        tbl_facs.add_column('Facility ID', header_style='bold yellow', style='yellow')
        tbl_facs.add_column('Added At', header_style='bold green', style='green')
        tbl_facs.add_column('Working', header_style='bold yellow')
    
        for zx in xasn.facilities:
            oper_note = '[bold][green]YES[/][/]' if zx.status.lower() == 'ok' else '[bold][red]NO[/][/]'
    
            tbl_facs.add_row(
                zx.name, zx.city, f"{zx.local_asn}", f"{zx.fac_id}", f"{zx.created}", oper_note
            )
        if not list_ixps:
            # print_std(xgrid(['', '', tbl_facs, ''], padding=(10, 10, 10, 10), column_kwargs=dict(justify='center')))
            print_std(
                Columns(
                    [tbl_facs],
                    # padding=(10, 10, 10, 10),
                    # padding=(20, 0, 0, 0),
                    # width=150,
                    align='center',
                    equal=False, expand=False
                )
            )

        # print_std(tbl_facs)
        # print_std()
    
    if tbl_facs and tbl_ix:
        # print_std(xgrid(['', tbl_ix, tbl_facs, ''], padding=(10, 10, 10, 10), column_kwargs=dict(justify='center')))
        tbl_ix.columns[0].overflow = 'fold'
        tbl_facs.columns[0].overflow = 'fold'
        print_std(Columns([tbl_ix, tbl_facs]))

    print_std()


def cmd_asinfo_raw(opt: argparse.Namespace):
    asn: int = extract_number(opt.asn, int)
    
    out_format: str = opt.out_format.lower()
    destination: str = opt.destination
    pretty: bool = opt.pretty
    
    only_ixps, only_facs = opt.only_ixps, opt.only_facs
    list_ixps, list_facs = opt.list_ixps, opt.list_facs
    depth = 3 if any([list_ixps, list_facs, only_ixps, only_facs]) else 0
    xasn = lookup_asn(asn, depth)[0]
    
    if only_ixps:
        res = [dict(ix) for ix in xasn.ixps]
    elif only_facs:
        res = [dict(fc) for fc in xasn.facilities]
    else:
        res = dict(xasn)
    res = purge_parent(res)
    if out_format in ['js', 'jsn', 'json']:
        fres = json.dumps(res, indent=4 if pretty else None)
        fmt_ext = 'json'
    elif out_format in ['y', 'yml', 'yaml', 'ym', 'yl']:
        fres = yaml.safe_dump(res)
        fmt_ext = 'yaml'
    elif out_format in ['xml', 'xm', 'x', 'htm', 'html', 'ml']:
        fres = stringify(dicttoxml(res))
        fmt_ext = 'xml'
        if pretty:
            zdom = minidom.parseString(fres)
            fres = zdom.toprettyxml()
    else:
        raise ValueError(f"Output format {out_format!r} is not a valid output format.")
    
    if empty(destination, itr=True) or destination in ['', '-', '/dev/stdout']:
        if pretty:
            print_std(fres)
        else:
            sys.stdout.write(fres)
            sys.stdout.flush()
    else:
        print_err(f"[yellow]Writing generated {fmt_ext.upper()!r} data to file:[/] {destination!r}")
        with open(destination, 'w') as fh:
            fh.write(fres)
        print_err(f"[green]Successfully wrote {fmt_ext.upper()!r} data to file:[/] {destination!r}")


def cmd_neigh(opt: argparse.Namespace):
    asn: int = extract_number(opt.asn, int)
    output: Optional[str] = opt.output
    output = Path(output).expanduser().resolve() if not empty(output) else output
    pretty: bool = opt.pretty
    xasn = lookup_asn(asn)[0]
    if empty(opt.ixp_name):
        ixlist = xasn.ixps
    else:
        ixlist = xasn.find_ixps(opt.ixp_name, exact=opt.exact)
    if opt.limit > 0:
        ixlist = ixlist[:opt.limit]
    
    kargs = dict(
        port='', lock_version=opt.lock_version,
        os=opt.os, peer_template=opt.peer_template, peer_policy_v4=opt.peer_policy_v4,
        peer_policy_v6=opt.peer_policy_v6, peer_session=opt.peer_session,
        trim_name=opt.trim_name, trim_words=opt.trim_words,
        use_max_prefixes=opt.use_max_prefixes
        # use_max_prefixes=True, max_prefixes_v4=None, max_prefixes_v6=None,
        # max_prefix_config=None
    )
    if not empty(opt.as_name): kargs['as_name'] = opt.as_name
    if not empty(opt.max_prefixes_v4): kargs['max_prefixes_v4'] = opt.max_prefixes_v4
    if not empty(opt.max_prefixes_v6): kargs['max_prefixes_v6'] = opt.max_prefixes_v6

    for idx, ix in enumerate(ixlist):
        nb = generate_neigh(
            ix, xasn, peer_idx=idx + 1, **kargs
        )
        if not empty(output):
            print_err(f"[yellow]Writing neighbour config to file:[/] {output!s}")
            with open(output, 'w') as fh:
                fh.write(nb)
            print_err(f"[green]Successfully wrote neighbour config to file:[/] {output!s}")
        else:
            if pretty:
                print_std(nb)
            else:
                sys.stdout.write(nb)
                sys.stdout.flush()


def cmd_sync(opt: argparse.Namespace = None):
    print_err('[cyan]Running update_db() - attempting to sync PeeringDB to our local DB...[/]')
    res = update_db(settings.PDB_CONFIG)
    print_err("[yellow]Result from update_db():[/]", res)
    print_err('[green] +++ Finished running update_db() - Synced PeeringDB to our local DB :) +++ [/]')
    return 0


def cmd_dump_config(opt: argparse.Namespace = None):
    out = opt.output if opt else None
    if not empty(out) and out not in ['', '-', '/dev/stdout']:
        out = Path(out).expanduser().resolve()
        print_err("[yellow]Outputting dumped config to file:[/]", out)
    cfg = settings.dump_config()
    if empty(out) or out in ['', '-', '/dev/stdout']:
        print_std(cfg)
    if not empty(out) and out not in ['', '-', '/dev/stdout']:
        with open(out, 'w') as fh:
            fh.write(cfg)
        print_err("[green]Successfully dumped config to file:[/]", out)


def cmd_conf_gen(opt: argparse.Namespace):
    out = opt.output
    cfgtype = opt.name
    
    ex_path = settings.APP_DIR / 'extras' / CFGTYPE_MAP.get(cfgtype, cfgtype)
    
    if not ex_path.exists():
        print_err(f'[red]ERROR: Config file {ex_path!s} does not exist![/]')
        return 5
    
    if not empty(out) and out not in ['', '-', '/dev/stdout']:
        out = Path(out).expanduser().resolve()
        print_err("[yellow]Outputting dumped config to file:[/]", out)
    
    with open(ex_path, 'r') as exmp_fh:
    
        cfg = exmp_fh.read()
        
        if empty(out) or out in ['', '-', '/dev/stdout']:
            print_std(cfg)
        
        if not empty(out) and out not in ['', '-', '/dev/stdout']:
            with open(out, 'w') as fh:
                fh.write(cfg)
            print_err("[green]Successfully dumped config to file:[/]", out)
    return 0


def main():
    parser = ErrHelpParser(
        sys.argv[0],
        description=textwrap.dedent("""
        Neighbour Peering Generator
        
        A tool to display ASN peering information, generate BGP neighbour configs for datacenter routers/switches,
        and more - by querying PeeringDB.com.
        
        (C) 2021 Privex Inc. - https://www.privex.io
        Official Repo: https://github.com/Privex/neighgen
        """),
        epilog=textwrap.dedent(f"""
        
        
        Examples:
        
            ##############
            # asinfo
            ##############
            Display PeeringDB information for AS210083 (Privex) as pretty printed tables:
            
                {sys.argv[0]} asinfo 210083
            
            Display PeeringDB information for AS210083 (Privex) as pretty printed tables,
            and include internet exchange information:
            
                {sys.argv[0]} asinfo -x 210083
            
            Display PeeringDB information for AS210083 (Privex) as pretty printed tables,
            and include both internet exchange information, and facility information:
            
                {sys.argv[0]} asinfo -x -F as210083
            
            ##############
            # asinfo-raw
            ##############
            
            Display PeeringDB info for AS210083 in programmatic form - which by default is JSON:
            
                {sys.argv[0]} asinfo-raw 210083
            
            Display PeeringDB info for AS210083 in programmatic form, including both IXP and facility info:
                
                {sys.argv[0]} asinfo-raw -x -F 210083
            
            Display ONLY IXP information from PeeringDB for AS210083 in programmatic form:

                {sys.argv[0]} asinfo-raw -OX 210083
            
            Display ONLY Facility information from PeeringDB for AS210083 in programmatic form:

                {sys.argv[0]} asinfo-raw -OF 210083
            
            Display ONLY IXP information from PeeringDB for AS210083 in programmatic form - but as YAML
            instead of JSON:

                {sys.argv[0]} asinfo-raw -OX 210083 yml
            
            Display PeeringDB info for AS210083 in programmatic form, including both IXP and facility info,
            but as XML instead of JSON:

                {sys.argv[0]} asinfo-raw -x -F 210083 xml
           
            ##############
            # neigh
            ##############
            
            Display neighbour configuration for peering with AS210083 at all of their IXPs,
            using the default OS config format 'nxos' (Cisco NX-OS):
            
                {sys.argv[0]} neigh 210083
            
            Display neighbour configuration for peering with AS210083 at only exchanges with 'ams-ix'
            in their name, using the default OS config format 'nxos' (Cisco NX-OS):
            
                {sys.argv[0]} neigh 210083 ams-ix
            
            Display neighbour configuration for peering with AS210083 at only exchanges with 'ams-ix'
            in their name, this time we manually specify that we want the config to be formatted
            for use with 'ios' (Cisco IOS).
            
                {sys.argv[0]} neigh -o ios 210083 ams-ix
            
            Same as previous, but we set the peer-policy for v4 and v6 to blank, which disables
            it from adding peer-policy neighbour commands:
            
                {sys.argv[0]} neigh -p4 '' -p6 '' -o ios 210083 ams-ix
            
            The network AS13335 peers at several different AMS-IX regions, so to limit the neighbours to
            use only the IXP called "AMS-IX", and not "AMS-IX Hong Kong" or "AMS-IX Caribbean",
            we use "-X" to enable exact IXP matching (the matching isn't case sensitive though).
            This ensure it only uses IXP peers on the exchange named "AMS-IX" and not their
            other regions.
            
                {sys.argv[0]} neigh -X 13335 ams-ix
            
        """), formatter_class=argparse.RawTextHelpFormatter
    )
    parser.set_defaults(cmd=None)
    sp = parser.add_subparsers()
    
    sync_parser = sp.add_parser('sync', help='Sync PeeringDB to our local DB')
    sync_parser.set_defaults(cmd=cmd_sync)

    dump_config_parser = sp.add_parser('dump_config', help='Dump the running config from memory as YAML')
    dump_config_parser.add_argument(
        '-o', '--output', '--destination', dest='output', default=None,
        help='File/device to output the generated data to. Defaults to blank - which writes to stdout.'
    )
    dump_config_parser.set_defaults(cmd=cmd_dump_config)
    conf_gen = sp.add_parser('gen_config', help='Reads an example config from neighgen/extras, for you to generate a base config')
    conf_gen.add_argument(
        'name', choices=CFGTYPE_MAP,
        help=f"Select which type of example config you want to generate. Choices: {', '.join(CFGTYPE_MAP.keys())}"
    )
    conf_gen.add_argument(
        '-o', '--output', '--destination', dest='output', default=None,
        help='File/device to output the generated data to. Defaults to blank - which writes to stdout.'
    )
    conf_gen.set_defaults(cmd=cmd_conf_gen)

    asparser = sp.add_parser('asinfo', help='Outputs info about a given ASN')
    asparser.add_argument('asn')
    asparser.add_argument(
        '-x', '--exchanges', '--list-exchanges', action='store_true', dest='list_ixps', default=False,
        help='Display a table of IXPs which the given ASN is a member of. Disabled by default.'
    )
    asparser.add_argument(
        '-F', '--facilities', '--list-facilities', action='store_true', dest='list_facs', default=False,
        help='Display a table of facilities which the given ASN is present within. Disabled by default.'
    )
    asparser.set_defaults(cmd=cmd_asinfo)

    raw_asparser = sp.add_parser('asinfo-raw', help='Outputs info about a given ASN as JSON, XML, or YML')
    raw_asparser.add_argument('asn')
    raw_asparser.add_argument('out_format', default='json', choices=[
        'js', 'jsn', 'json', 'y', 'yml', 'yaml', 'ym', 'yl', 'xml', 'xm', 'x', 'htm', 'html', 'ml'
    ], nargs='?')
    raw_asparser.add_argument(
        '-o', '--output', '--destination', dest='destination', default=None,
        help='File/device to output the generated data to. Defaults to blank - which writes to stdout.'
    )
    raw_asparser.add_argument(
        '-x', '--exchanges', '--list-exchanges', action='store_true', dest='list_ixps', default=False,
        help='Display a table of IXPs which the given ASN is a member of. Disabled by default.'
    )
    raw_asparser.add_argument(
        '-F', '--facilities', '--list-facilities', action='store_true', dest='list_facs', default=False,
        help='Display a table of facilities which the given ASN is present within. Disabled by default.'
    )
    raw_asparser.add_argument(
        '-OX', '--only-exchanges', '--only-ixps', action='store_true', dest='only_ixps', default=False,
        help="Print ONLY information about the ASN's exchanges."
    )
    raw_asparser.add_argument(
        '-OF', '--only-facilities', '--only-facs', action='store_true', dest='only_facs', default=False,
        help="Print ONLY information about the ASN's facilities."
    )
    raw_asparser.add_argument(
        '-np', '--no-pretty', '--flat', action='store_false', dest='pretty', default=True,
        help='Disable pretty printing - print raw JSON/YML/XML'
    )
    raw_asparser.set_defaults(cmd=cmd_asinfo_raw)

    neighparser = sp.add_parser('neigh', help='Generate a BGP neighbour config for a given ASN via PeeringDB')
    neighparser.add_argument('asn')
    neighparser.add_argument('ixp_name', nargs='?', default=None)
    neighparser.add_argument('-X', '--exact-match', default=False, action='store_true', dest='exact',
                             help=f"Match ixp_name against IXP names EXACTLY.")
    neighparser.add_argument('-L', '--limit', default=0, type=int, dest='limit',
                             help=f"Set to a number >=1 to limit how many IXPs can be matched by the query. "
                                  f"This defaults to 0 (unlimited IXPs can match).")

    neighparser.add_argument(
        '-np', '--no-pretty', '--flat', action='store_false', dest='pretty', default=True,
        help='Disable pretty printing - print raw JSON/YML/XML'
    )
    
    neighparser.add_argument('-o', '--os', default=settings.appcfg.default_os, choices=list(appcfg.template_map.keys()),
                             help=f"The OS to generate the config for. Options: {', '.join(appcfg.template_map.keys())}")
    neighparser.add_argument('-f', '--output', default=None, dest='output',
                             help=f"The file/device to output the generated neighbour config to. By default, this is blank, "
                                  f"which means the config will be outputted to stdout.")
    neighparser.add_argument('-pt', '--peer-template', default=appcfg.peer_template, dest='peer_template',
                             help=f"The name of the peer template to use. Default: {appcfg.peer_template}")
    neighparser.add_argument('-ps', '--peer-session', default=appcfg.peer_session, dest='peer_session',
                             help=f"The name of the peer session to use. Default: {appcfg.peer_session}")
    neighparser.add_argument('-p4', '--peer-policy-v4', default=appcfg.peer_policy_v4, dest='peer_policy_v4',
                             help=f"The name of the IPv4 peer policy to use. Default: {appcfg.peer_policy_v4}")
    neighparser.add_argument('-p6', '--peer-policy-v6', default=appcfg.peer_policy_v6, dest='peer_policy_v6',
                             help=f"The name of the IPv6 peer policy to use. Default: {appcfg.peer_policy_v6}")
    
    neighparser.add_argument('-an', '--as-name', default=None, dest='as_name',
                             help=f"Use a manually specified Network Name instead of using the one from PeeringDB")
    
    neighparser.add_argument('-T', '--trim-name', default=appcfg.ix_trim, action='store_true', dest='trim_name',
                             help=f"Trim the IXP's name down to trim-words (default: {appcfg.ix_trim})")
    neighparser.add_argument('-Tw', '--trim-words', default=appcfg.ix_trim_words, dest='trim_words',
                             help=f"The number of words to trim the IXP's name down to (if trim-name is enabled) "
                                  f"(default: {appcfg.ix_trim_words})")
    
    neighparser.add_argument('-mp', '--use-max-prefixes', default=appcfg.max_prefixes.use, action='store_true', dest='use_max_prefixes',
                             help=f"Enable adding max-prefixes limit commands (default: {appcfg.max_prefixes.use})")
    neighparser.add_argument('-mp4', '--max-prefixes-v4', default=None, type=int, dest='max_prefixes_v4',
                             help=f"Set number of IPv4 max prefixes to limit to (if specified, will not use peeringdb value)")
    neighparser.add_argument('-mp6', '--max-prefixes-v6', default=None, type=int, dest='max_prefixes_v6',
                             help=f"Set number of IPv6 max prefixes to limit to (if specified, will not use peeringdb value)")
    
    neighparser.add_argument('-lv', '--lock-version', default=appcfg.lock_version, action='store_true', dest='lock_version',
                             help=f"Disables the opposite address version in each neighbor (Default: {appcfg.lock_version})")
    neighparser.add_argument('-ulv', '--unlock-version', default=appcfg.lock_version, action='store_false', dest='lock_version',
                             help=f"Does NOT disable the opposite address version in each neighbor (Default: {appcfg.lock_version})")
    neighparser.set_defaults(cmd=cmd_neigh)
    
    zargs = parser.parse_args()
    if not zargs.cmd:
        return parser.error("No subcommand specified")
    return zargs.cmd(zargs)

    
def run_main():
    mainres = main()
    if isinstance(mainres, int): sys.exit(mainres)
    return sys.exit(0)


if __name__ == '__main__':
    run_main()
