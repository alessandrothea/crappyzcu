#!/usr/bin/env python
import json
import time
import sys, subprocess
import click
import rich
import logging
import os

from rich import print
from rich.table import Table
from rich.logging import RichHandler
from rich.progress import track

from crappyhalclient import CrappyHardwareClient


MAX_MGT=2
# N_SRC=8
# N_SRCS_P_MGT = N_SRC//N_MGT


# -----------------------------------------------------------------------------
# Utilities
def dict_to_table( vals: dict, **kwargs):

    t = Table(**kwargs)
    t.add_column('name')
    t.add_column('value', style='green')
    for k,v in vals.items():
        t.add_row(k,hex(v))
    return t

def read_regs(hw, reg_list):
    d = {}
    for r in reg_list:
        v = hw.read(r)
        d[r] = v
    return d

def read_and_print(hw, reg_list):
    d = {}
    for r in reg_list:
        v = hw.read(r)
        d[r] = v
    print(dict_to_table(d))

# -----------------------------------------------------------------------------

ctrl_hosts = [
    'np04-zcu-001',
    'np04-wib-503'
]

port = 5556
# addrtab = 'zcu_top.flat_regmap.json'
addrtab = os.path.join(os.environ['CRAPPYZCU_SHARE'], 'config', 'hermes_zcu_mark3', 'zcu_top.xml')

mgts_all = tuple(str(i) for i in range(MAX_MGT))

@click.command()
@click.argument('ctrl_id', type=click.Choice(ctrl_hosts))
@click.option('-m', '--mgts', 'sel_mgts', type=click.Choice(mgts_all), multiple=True, default=None)
def main(ctrl_id, sel_mgts):
    """Simple program that greets NAME for a total of COUNT times."""


    hw = CrappyHardwareClient(ctrl_id, port, addrtab)
    hw.connect()

    magic = hw.read('tx.info.magic')
    if magic != 0xdeadbeef:
        raise ValueError(f"Magic number check failed. Expected '0xdeadbeef', read '{hex(magic)}'")

    n_mgt = hw.read('tx.info.generics.n_mgts')
    n_src = hw.read('tx.info.generics.n_srcs')
    ref_freq = hw.read('tx.info.generics.ref_freq')

    mgts = list(range(n_mgt))
    
    # deal with defaults
    if not sel_mgts:
        sel_mgts = mgts
    else:
        sel_mgts = [int(s) for s in sel_mgts]


    # Check for existance
    if not set(sel_mgts).issubset(mgts):
        print(sel_mgts, mgts)
        raise ValueError(f"MGTs {set(sel_mgts)-set(mgts)} are not instantiated")
    
    # mgts = [int(s) for s in (mgts if mgts else [0])]


    print('Resetting tx_mux')
    hw.write('tx.mux.csr.ctrl', 0x0)
    print('Done')

    hw.write('tx.mux.csr.ctrl.en', True)
    hw.write('tx.mux.csr.ctrl.en_buf', True)
    hw.write('tx.mux.csr.ctrl.tx_en', True)

    hw.write('tx.mux.csr.ctrl.sample', True)
    time.sleep(0.1)
    hw.write('tx.mux.csr.ctrl.sample', False)


    # print('---Reading info regs---')
    ctrl_i =read_regs(hw, hw.get_regs('tx.info.*'))
    # print('---Reading ctrl regs---')
    ctrl_d =read_regs(hw, hw.get_regs('tx.mux.csr.ctrl.*'))


    # print('---Reading stat regs---')
    stat_d =read_regs(hw, hw.get_regs('tx.mux.csr.stat.*'))

    grid = Table(title="tx_mux", show_edge=False, show_header=False, show_lines=False, pad_edge=False, padding=0)
    grid.add_column("info")
    grid.add_column("ctrl")
    grid.add_column("stat")
    grid.add_row(dict_to_table(ctrl_i), dict_to_table(ctrl_d), dict_to_table(stat_d))
    print(grid)


    n_srcs_p_mgt = n_src//n_mgt

    for i in sel_mgts:
        print()
        print()
        print(f'---Reading Mux {i}---')
        hw.write('tx.mux.csr.ctrl.sel_mux',i)
        stat_regs = (
            [ n for n in hw.addrtab if n.startswith('tx.mux.mux.stat') ] +
            []
            )

        read_and_print(hw, stat_regs)

        d = {}
        src_ids = tuple(range(n_srcs_p_mgt*i, n_srcs_p_mgt*(i+1)))
        for j in track(src_ids, description='Reading buffer status'):
            hw.write('tx.mux.csr.ctrl.sel_buf',j)
            stat_regs = (
                [ n for n in hw.addrtab if n.startswith('tx.mux.buf') ] +
                []
                )
                
            d[j] = read_regs(hw, stat_regs)

        # Create the summary table
        t = Table()

        # Add 1 column for the reg name, and as many as the number of sources
        t.add_column('name')
        for j in src_ids:
            t.add_column(f'Buf {j}', style='green')

        # Unify the reg list (useless?)
        reg_names = set()
        for k,v in d.items():
            reg_names = reg_names.union(v.keys())
        
        for n in sorted(reg_names):
            t.add_row(n,*(hex(d[j][n]) for j in src_ids))
        print(t)
        


if __name__ == '__main__':
    FORMAT = "%(message)s"
    logging.basicConfig(
        level="WARN", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
    )
    main()