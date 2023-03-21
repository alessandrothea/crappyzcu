#!/usr/bin/env python

import click
import os
import socket
import time
from rich import print
from rich.table import Table
from rich.progress import track

from crappyhalclient import CrappyHardwareClient

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


rx_endpoints = {
    'np02-srv-001:priv': {
        'mac': 0xd85ed38cc4e3,
        'ip': 0xc0a80201, # 192.168.2.1
        'port': 0x4444,
    },
    'np02-srv-001-100G': {
        'mac': 0x6cfe5447a128,
        'ip': 0x0a498b16, # 10.73.139.22
        'port': 0x4444,
    },
    'np04-srv-021-100G': {
        'mac': 0xec0d9a8eba10,
        'ip': 0x0a49883c, # 10.73.139.16
        'port': 0x4444,
    },
}

tx_endpoints = {
    'np04-zcu-001:priv': {
        'mac': 0x000a3504b5f7,
        'ip': 0xc0a80202, # 192.168.2.2
        'port': 0x4444,
    },
    'np04-zcu-001-10G': {
        'mac': 0x80d3360052ff,
        'ip': 0x0a498b17, # 10.73.139.23
        'port': 0x4444,
    },
    'np04-wib-503-d0': {
        'mac': 0x80d336005254,
        'ip': 0x0a498b18, # 10.73.139.23
        'port': 0x4444,
    },
    'np04-wib-503-d1': {
        'mac': 0x80d336005255,
        'ip': 0x0a498b19, # 10.73.139.23
        'port': 0x4444,
    }
}


ctrl_hosts = [
    'np04-zcu-001',
    'np04-wib-503'
]
port = 5556
# addrtab = os.path.join(os.environ['CRAPPYZCU_SHARE'], 'config', 'hermes_zcu_mark3', 'zcu_top.xml')
# addrtab = os.path.join(os.environ['CRAPPYZCU_SHARE'], 'config', 'hermes_zcu_v0.9.0', 'zcu_top.xml')
addrtab = os.path.join(os.environ['CRAPPYZCU_SHARE'], 'config', 'hermes_zcu_v0.9.1_b0', 'zcu_top.xml')

# N_MGT=4
# N_SRC=8
# N_SRCS_P_MGT = N_SRC//N_MGT
MAX_MGT=2
MAX_SRCS_P_MGT =16
mgts_all = tuple(str(i) for i in range(MAX_MGT))

class CrappyObj:
    pass

@click.group(chain=True)
@click.argument('ctrl_id', type=click.Choice(ctrl_hosts))
@click.pass_context
def main(ctx, ctrl_id):
    obj = CrappyObj

    obj.hw = CrappyHardwareClient(ctrl_id, port, addrtab)
    # print(obj.hw.addrtab)
    obj.hw.connect()
    print(f"Connected to '{ctrl_id}'")
    magic = obj.hw.read('tx.info.magic')
    if magic != 0xdeadbeef:
        raise ValueError(f"Magic number check failed. Expected '0xdeadbeef', read '{hex(magic)}'")

    n_mgt = obj.hw.read('tx.info.generics.n_mgts')
    n_src = obj.hw.read('tx.info.generics.n_srcs')
    ref_freq = obj.hw.read('tx.info.generics.ref_freq')




    obj.n_mgt = n_mgt
    obj.n_src = n_src
    obj.ref_freq = ref_freq

    ctx.obj = obj

@main.command()
@click.option('--en/--dis', 'enable', default=None)
@click.option('--buf-en/--buf-dis', 'buf_en', default=None)
@click.option('--tx-en/--tx-dis', 'tx_en', default=None)
@click.option('-l', '--link', type=int, default=0)
@click.pass_obj
def enable(obj, enable, buf_en, tx_en, link):
    hw = obj.hw
    n_mgt = obj.n_mgt

    if link >= n_mgt:
        raise ValueError(f"MGT {link} not instantiated")
    hw.write('tx.csr.ctrl.sel',link)

    print(f"Setting {link} en:{enable}, buf_en: {buf_en}, tx_en: {tx_en}")
    if enable is not None:
        hw.write('tx.mux.csr.ctrl.en', enable)

    if buf_en is not None:
        hw.write('tx.mux.csr.ctrl.en_buf', buf_en)

    if tx_en is not None:
        hw.write('tx.mux.csr.ctrl.tx_en', tx_en)


    # print('---Reading ctrl regs---')
    ctrl_d =read_regs(hw, hw.get_regs('tx.mux.csr.ctrl.*'))
    print(
        dict_to_table(ctrl_d, title='tx_mux ctrl'), 
    )


@main.command("mux-config")
@click.argument('detid', type=int)
@click.argument('crate', type=int)
@click.argument('slot', type=int)
@click.option('-l', '--link', type=int, default=0)
@click.pass_obj
def mux_config(obj, detid, crate, slot, link):
    """Comfigure the UDP blocks """

    hw = obj.hw

    n_mgt = obj.n_mgt
    n_src = obj.n_src
    n_srcs_p_mgt = n_src//n_mgt

    if link >= n_mgt:
        raise ValueError(f"Link {link} not instantiated")
    
    hw.write('tx.csr.ctrl.sel',link)
    hw.write('tx.mux.mux.ctrl.detid', detid)
    hw.write('tx.mux.mux.ctrl.crate', crate)
    hw.write('tx.mux.mux.ctrl.slot', slot)

    ctrl_mux =read_regs(hw, hw.get_regs('tx.mux.mux.ctrl.*'))
    print(ctrl_mux)

@main.command("udp-config")
@click.argument('src_id', type=click.Choice(tx_endpoints.keys()))
@click.argument('dst_id', type=click.Choice(rx_endpoints.keys()))
@click.option('-l', '--link', type=int, default=0)
@click.pass_obj
def udp_config(obj, src_id, dst_id, link):
    """Comfigure the UDP blocks """


    n_mgt = obj.n_mgt

    if link >= n_mgt:
        raise ValueError(f"Link {link} not instantiated")


    hw = obj.hw

    dst = rx_endpoints[dst_id]
    src = tx_endpoints[src_id]

    udp_core_ctrl = f'tx.udp.udp_core_{link}.udp_core_control.nz_rst_ctrl'
    hw.write(f'{udp_core_ctrl}.filter_control', 0x07400307)

    # Our IP address = 10.73.139.23
    print(f"Our ip address: {socket.inet_ntoa(src['ip'].to_bytes(4, 'big'))}")
    hw.write(f'{udp_core_ctrl}.src_ip_addr', src['ip']) 
    # Their IP address = 10.73.139.23
    print(f"Their ip address: {socket.inet_ntoa(dst['ip'].to_bytes(4, 'big'))}")
    hw.write(f'{udp_core_ctrl}.dst_ip_addr', dst['ip']) 
    # Our MAC address
    # Dest MAC address
    print(f"Our mac address: 0x{src['mac']:012x}")
    hw.write(f'{udp_core_ctrl}.src_mac_addr_lower', src['mac'] & 0xffffffff) 
    hw.write(f'{udp_core_ctrl}.src_mac_addr_upper', (src['mac'] >> 32) & 0xffff) 

    # Dest MAC address
    print(f"Their mac address: 0x{dst['mac']:012x}")
    hw.write(f'{udp_core_ctrl}.dst_mac_addr_lower', dst['mac'] & 0xffffffff) 
    hw.write(f'{udp_core_ctrl}.dst_mac_addr_upper', (dst['mac'] >> 32) & 0xffff) 

    # Ports
    hw.write(f'{udp_core_ctrl}.udp_ports.src_port', src['port']) 
    hw.write(f'{udp_core_ctrl}.udp_ports.dst_port', dst['port']) 


@main.command("zcu-src-config")
@click.option('-l', '--link', type=int, default=0)
@click.option('-n', '--en-n-src', type=click.IntRange(0, MAX_SRCS_P_MGT), default=1)
@click.option('-d', '--dlen', type=click.IntRange(0, 0xfff), default=0x382)
@click.option('-r', '--rate-rdx', type=click.IntRange(0, 0x3f), default=0xa)
@click.pass_obj
def zcu_src_config(obj, link, en_n_src, dlen, rate_rdx):
    """Configure trivial data sources"""

    hw = obj.hw

    n_mgt = obj.n_mgt
    n_src = obj.n_src
    n_srcs_p_mgt = n_src//n_mgt

    if link >= n_mgt:
        raise ValueError(f"MGT {link} not instantiated")
    
    if en_n_src > n_srcs_p_mgt:
        raise ValueError(f"{en_n_src} must be lower than the number of generators per link ({n_srcs_p_mgt})")

    for i in range(n_srcs_p_mgt):
        src_id = n_srcs_p_mgt*link+i
        hw.write(f'ctrl.sel', src_id)
        src_en = (i<en_n_src)
        print(f'Configuring generator {src_id} : {src_en}')
        hw.write(f'src.ctrl.en', src_en)
        if not src_en:
            continue
        ## Number of words per block
        hw.write(f'src.ctrl.dlen', dlen)
        ## ????
        hw.write(f'src.ctrl.rate_rdx', rate_rdx) 



    # for i in range(n_srcs_p_mgt):
    #     gen_id = n_srcs_p_mgt*mgt+i
    #     hw.write(f'ctrl.sel', gen_id)
    #     gen_en = (i<n_gen)
    #     print(f'Configuring generator {gen_id} : {gen_en}')
    #     hw.write(f'src.ctrl.en', gen_en)
    #     if not gen_en:
    #         continue
    #     ## ????
    #     hw.write(f'src.ctrl.dlen', 0x382)
    #     ## ????
    #     hw.write(f'src.ctrl.rate_rdx', 0xa) 


@main.command("fakesrc-config")
@click.option('-l', '--link', type=int, default=0)
@click.option('-n', '--n-src', type=click.IntRange(0, MAX_SRCS_P_MGT), default=1)
@click.option('-l', '--dlen', type=click.IntRange(0, 0xfff), default=0x382)
@click.option('-r', '--rate-rdx', type=click.IntRange(0, 0x3f), default=0xa)
@click.pass_obj
def src_config(obj, link, n_src, dlen, rate_rdx):
    """Configure trivial data sources"""

    hw = obj.hw

    n_mgt = obj.n_mgt
    n_src = obj.n_src
    n_srcs_p_mgt = n_src//n_mgt

    if link >= n_mgt:
        raise ValueError(f"MGT {link} not instantiated")
    
    if n_src > n_srcs_p_mgt:
        raise ValueError(f"{n_src} must be lower than the number of generators per link ({n_srcs_p_mgt})")

    for src_id in range(n_srcs_p_mgt):
        hw.write('tx.csr.ctrl.sel_buf', src_id)
        was_en = hw.read('tx.csr.ctrl.en_buf')
        # disable buffer before reconfiguring "or bad things will happen"
        hw.write('tx.csr.ctrl.en_buf', 0x0)

        src_en = (src_id<n_src)
        print(f'Configuring generator {src_id} : {src_en}')
        hw.write(f'tx.buf.ctrl.fake_en', src_en)
        if not src_en:
            continue
        ## ????
        hw.write(f'tx.buf.ctrl.dlen', dlen)
        ## ????
        hw.write(f'tx.buf.ctrl.rate_rdx', rate_rdx) 
        hw.write('tx.csr.ctrl.sel_buf', was_en)


@main.command()
@click.pass_obj
@click.option('-l', '--links', 'sel_links', type=click.Choice(mgts_all), multiple=True, default=None)
@click.option('-s', '--seconds', type=int, default=2)
def stats(obj, sel_links, seconds):
    """Simple program that greets NAME for a total of COUNT times."""

    hw = obj.hw

    n_src = obj.n_src
    n_mgt = obj.n_mgt
    n_srcs_p_mgt = n_src//n_mgt

    mgts = list(range(n_mgt))
    
    # deal with defaults
    if not sel_links:
        sel_links = mgts
    else:
        sel_links = [int(s) for s in sel_links]


    # Check for existance
    if not set(sel_links).issubset(mgts):
        print(sel_links, mgts)
        raise ValueError(f"MGTs {set(sel_links)-set(mgts)} are not instantiated")
    
    # mgts = [int(s) for s in (mgts if mgts else [0])]

    print(f"seconds counters for {seconds}s")
    hw.write('tx.samp.ctrl.samp', True)
    time.sleep(seconds)
    hw.write('tx.samp.ctrl.samp', False)


    # print('---Reading info regs---')
    ctrl_i = read_regs(hw, hw.get_regs('tx.info.*'))

    # grid = Table.grid()
    # grid.add_column("info")
    # grid.add_column("ctrl")
    # grid.add_column("stat")
    # grid.add_row(
    #     dict_to_table(ctrl_i, title='tx_mux info'),
    #     dict_to_table(ctrl_d, title='tx_mux ctrl'), 
    #     dict_to_table(stat_d, title='tx mux stat'))
    print(dict_to_table(ctrl_i, title='tx_mux info'))


    n_srcs_p_mgt = n_src//n_mgt

    for i in sel_links:
        print()
        print()
        print(f'---Reading Tx Mux {i}---')
        hw.write('tx.csr.ctrl.sel',i)

        # print('---Reading ctrl regs---')
        ctrl_d = read_regs(hw, hw.get_regs('tx.mux.csr.ctrl.*'))

        # print('---Reading stat regs---')
        stat_d = read_regs(hw, hw.get_regs('tx.mux.csr.stat.*'))

        grid = Table.grid()
        grid.add_column("ctrl")
        grid.add_column("stat")
        grid.add_row(
            dict_to_table(ctrl_d, title='tx_mux ctrl'), 
            dict_to_table(stat_d, title='tx mux stat'))
        print(grid)


        ctrl_mux =read_regs(hw, hw.get_regs('tx.mux.mux.ctrl.*'))
        stat_mux =read_regs(hw, hw.get_regs('tx.mux.mux.stat.*'))

        grid = Table.grid()
        grid.add_column("ctrl")
        grid.add_column("stat")
        grid.add_row(
            dict_to_table(ctrl_mux, title="mux ctrl"),
            dict_to_table(stat_mux, title="mux stat"),
        )
        print(grid)

        stat_udp =read_regs(hw, hw.get_regs(f'tx.udp.udp_core_{i}.udp_core_control.packet_counters.*'))
        ctrl_udp =read_regs(hw, hw.get_regs(f'tx.udp.udp_core_{i}.udp_core_control.nz_rst_ctrl.(filter_control|src|dst|udp).*'))

        grid = Table.grid()
        grid.add_column("ctrl")
        grid.add_column("stat")
        grid.add_row(
            dict_to_table(ctrl_udp, title="udp ctrl"),
            dict_to_table(stat_udp, title="udp stat"),
        )
        print(grid)


        d = {}
        src_ids = tuple(range(n_srcs_p_mgt))
        for j in track(src_ids, description='Reading buffer status'):
            hw.write('tx.mux.csr.ctrl.sel_buf',j)
            d[j] = read_regs(hw, hw.get_regs('tx.mux.buf.*'))

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
    main()