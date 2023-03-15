#!/usr/bin/env python

import click
import os
import socket
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
addrtab = os.path.join(os.environ['CRAPPYZCU_SHARE'], 'config', 'hermes_zcu_mark3', 'zcu_top.xml')

# N_MGT=2
# N_SRC=8
# N_SRCS_P_MGT = N_SRC//N_MGT
MAX_SRCS_P_MGT =16

@click.command()
@click.argument('ctrl_id', type=click.Choice(ctrl_hosts))
@click.argument('src_id', type=click.Choice(tx_endpoints.keys()))
@click.argument('dst_id', type=click.Choice(rx_endpoints.keys()))
@click.option('-m', '--mgt', type=int, default=0)
@click.option('-n', '--n-gen', type=click.IntRange(0, MAX_SRCS_P_MGT), default=1)
def main(ctrl_id, src_id, dst_id, mgt, n_gen):

    hw = CrappyHardwareClient(ctrl_id, port, addrtab)
    hw.connect()

    magic = hw.read('tx.info.magic')
    if magic != 0xdeadbeef:
        raise ValueError(f"Magic number check failed. Expected '0xdeadbeef', read '{hex(magic)}'")

    n_mgt = hw.read('tx.info.generics.n_mgts')
    n_src = hw.read('tx.info.generics.n_srcs')
    ref_freq = hw.read('tx.info.generics.ref_freq')
    n_srcs_p_mgt = n_src//n_mgt

    if mgt >= n_mgt:
        raise ValueError(f"MGT {mgt} not instantiated")
    
    if n_gen > n_srcs_p_mgt:
        raise ValueError(f"{n_gen} must be lower than the number of generators per mgt ({n_srcs_p_mgt})")


    print('Disabling the tx mux block')
    hw.write('tx.mux.csr.ctrl', 0x0)

    dst = rx_endpoints[dst_id]
    src = tx_endpoints[src_id]

    udp_core_ctrl = f'tx.udp.udp_core_{mgt}.udp_core_control.nz_rst_ctrl'
    hw.write(f'{udp_core_ctrl}.filter_control', 0x07400307)
    # hw.write(f'{udp_core_ctrl}.filter_control', 0x0)

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


    hw.write('tx.mux.csr.ctrl.en', 0x0)
    hw.write('tx.mux.csr.ctrl.en_buf', 0x1)
    hw.write('tx.mux.csr.ctrl.tx_en', 0x0)

if __name__ == '__main__':
    main()