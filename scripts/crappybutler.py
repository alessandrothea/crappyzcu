#!/usr/bin/env python

import click
import os
from rich import print
from rich.table import Table
from rich.progress import track

from crappyhalclient import CrappyHardwareClient


phonebook = {
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

homes = {
    'np04-zcu-001:priv': {
        'mac': 0x000a3504b5f7,
        'ip': 0xc0a80202, # 192.168.2.2
        'port': 0x4444,
    },
    'np04-zcu-001-10G': {
        'mac': 0x80d3360052ff,
        'ip': 0x0a498b17, # 10.73.139.23
        'port': 0x4444,
    }
}

host = 'np04-zcu-001'
port = 5556
addrtab = os.path.join(os.environ['CRAPPYZCU_SHARE'], 'config', 'hermes_zcu_mark3', 'zcu_top.xml')

# N_MGT=2
# N_SRC=8
# N_SRCS_P_MGT = N_SRC//N_MGT
MAX_SRCS_P_MGT =16

@click.command()
@click.argument('src_id', type=click.Choice(homes.keys()))
@click.argument('dst_id', type=click.Choice(phonebook.keys()))
@click.option('-m', '--mgt', type=int, default=0)
@click.option('-n', '--n-gen', type=click.IntRange(0, MAX_SRCS_P_MGT), default=1)
def main(src_id, dst_id, mgt, n_gen):

    hw = CrappyHardwareClient(host, port, addrtab)
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


    print('Resetting the tmux')
    hw.write('tx.mux.csr.ctrl', 0x0)
    print('Done')

    dst = phonebook[dst_id]
    src = homes[src_id]

    udp_core_ctrl = f'tx.udp.udp_core_{mgt}.udp_core_control.nz_rst_ctrl'
    hw.write(f'{udp_core_ctrl}.filter_control', 0x07400307)
    # Our IP address = 10.73.139.23
    hw.write(f'{udp_core_ctrl}.src_ip_addr', src['ip']) 
    # Their IP address = 10.73.139.23
    hw.write(f'{udp_core_ctrl}.dst_ip_addr', dst['ip']) 
    # Dest MAC address
    hw.write(f'{udp_core_ctrl}.dst_mac_addr_lower', dst['mac'] & 0xffffffff) 
    hw.write(f'{udp_core_ctrl}.dst_mac_addr_upper', (dst['mac'] >> 32) & 0xffff) 

    # Ports
    hw.write(f'{udp_core_ctrl}.udp_ports.src_port', src['port']) 
    hw.write(f'{udp_core_ctrl}.udp_ports.dst_port', dst['port']) 

    for i in range(n_srcs_p_mgt):
        gen_id = n_srcs_p_mgt*mgt+i
        hw.write(f'ctrl.sel', gen_id)
        gen_en = (i<n_gen)
        print(f'Configuring generator {gen_id} : {gen_en}')
        hw.write(f'src.ctrl.en', gen_en)
        if not gen_en:
            continue
        ## ????
        hw.write(f'src.ctrl.dlen', 0x382)
        ## ????
        hw.write(f'src.ctrl.rate_rdx', 0xa) 


    hw.write('tx.mux.csr.ctrl.en', True)
    hw.write('tx.mux.csr.ctrl.en_buf', True)
    hw.write('tx.mux.csr.ctrl.tx_en', True)


# devmem.wreg(0x24c, [0x07400307]) # Turn off filters
# #devmem.wreg(0x209, [0xc0a80202]) # Our IP address = 192.168.2.2
# devmem.wreg(0x249, [0x0a498b17]) # Our IP address = 10.73.139.23
# #devmem.wreg(0x202, [0xd38cc4e3, 0x0000d85e]) # Dest MAC address = 0xd85ed38cc4e3
# devmem.wreg(0x242, [0x5447a128, 0x00006cfe]) # Dest MAC address = 0x6cfe5447a128
# #devmem.wreg(0x208, [0xc0a80201]) # Dest IP address = 192.168.2.1
# devmem.wreg(0x248, [0x0a498b16]) # Dest IP address = 10.73.139.22
# devmem.wreg(0x24a, [0x44444444]) # UDP ports 0x4444, 0x4444
# devmem.wreg(0x400, [0x4]) # Select source 0
# devmem.wreg(0x401, [0x000a3821]) # Enable source, every 2048 samples, 256 words
# devmem.wreg(0x400, [0x5]) # Select source 1
# devmem.wreg(0x401, [0x000a3821]) # Enable source, every 2048 samples, 256 words
# devmem.wreg(0x0, [0xb]) # Enable mux, bufs


# devmem.wreg(0x20c, [0x07400307]) # Turn off filters
# devmem.wreg(0x209, [0xc0a80202]) # Our IP address = 192.168.2.2
# devmem.wreg(0x202, [0xd38cc4e3, 0x0000d85e]) # Dest MAC address = 0xd85ed38cc4e3
# devmem.wreg(0x208, [0xc0a80201]) # Dest IP address = 192.168.2.1
# devmem.wreg(0x20a, [0x44444444]) # UDP ports 0x4444, 0x4444
# devmem.wreg(0x400, [0x0]) # Select source 0
# devmem.wreg(0x401, [0x000a3821]) # Enable source, every 2048 samples, 256 words
# devmem.wreg(0x400, [0x1]) # Select source 1
# devmem.wreg(0x401, [0x000a3821]) # Enable source, every 2048 samples, 256 words
# devmem.wreg(0x0, [0xb]) # Enable mux, bufs


if __name__ == '__main__':
    main()