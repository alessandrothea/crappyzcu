#!/usr/bin/env python

import click
import os
import socket
import time
import uhal
import logging
from rich import print
from rich.table import Table
from rich.logging import RichHandler


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


# -----------------------------------------------------------------------------
def dump_sub_regs(node):
    regs = {}
    for i in sorted(node.getNodes()):
        regs[i] = node.getNode(i).read()
    node.getClient().dispatch()

    return {k: v.value() for k, v in regs.items()}


# -----------------------------------------------------------------------------
def dump_reg(node):
    v = node.read()
    node.getClient().dispatch()
    return {node.getId(): v.value()}


class HermesController :
    def __init__(self, node):
        self.node = node

        self._load_info()
    

    def _load_info(self):
        magic = self.node.getNode('info.magic').read()
        self.node.getClient().dispatch()
        self.magic = magic.value()
        if self.magic != 0xdeadbeef:
            raise ValueError(f"Magic number check failed. Expected '0xdeadbeef', found '{hex(self.magic)}'")
        
        

        n_mgt = self.node.getNode('info.generics.n_mgts').read()
        n_src = self.node.getNode('info.generics.n_srcs').read()
        ref_freq = self.node.getNode('info.generics.ref_freq').read()
        self.node.getClient().dispatch()

        # Generics
        self.n_mgt = n_mgt.value()
        self.n_src = n_src.value()
        self.ref_freq = ref_freq.value()
        # Extra info
        self.n_srcs_p_mgt = self.n_src//self.n_mgt

    def get_node(self, id):
        return self.node.getNode(id)
    
    def dispatch(self):
        self.node.getClient().dispatch()

    def sample_ctrs(self, seconds: int):
        self.node.getNode('samp.ctrl.samp').write(True)
        self.node.getClient().dispatch()
        time.sleep(seconds)
        self.node.getNode('samp.ctrl.samp').write(False)
        self.node.getClient().dispatch()


    def sel_tx_mux(self, i: int):

        if i >= self.n_mgt:
            raise ValueError(f"Link {i} does not exist ({self.n_mgt})")
    
        self.node.getNode('csr.ctrl.sel').write(i)
        self.node.getClient().dispatch()


    def sel_tx_mux_buf(self, i: int):

        if i >= self.n_src:
            raise ValueError(f"Input buffer {i} does not exist ({self.n_src})")
        
        self.node.getNode('mux.csr.ctrl.sel_buf').write(i)
        self.node.getClient().dispatch()

    

# -----------------------------------------------------------------------------
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

    ### WIB 501
    'np04-wib-501-d0': {
        'mac': 0x80d336005250,
        'ip': 0x0a498b1e, # 10.73.139.30
        'port': 0x4444,
    },
    'np04-wib-501-d1': {
        'mac': 0x80d336005251,
        'ip': 0x0a498b1f, # 10.73.139.31
        'port': 0x4444,
    },

    ### WIB 502
    'np04-wib-502-d0': {
        'mac': 0x80d336005252,
        'ip': 0x0a498b20, # 10.73.139.32
        'port': 0x4444,
    },
    'np04-wib-502-d1': {
        'mac': 0x80d336005253,
        'ip': 0x0a498b21, # 10.73.139.33
        'port': 0x4444,
    },


    ### WIB 503
    'np04-wib-503-d0': {
        'mac': 0x80d336005254,
        'ip': 0x0a498b18, # 10.73.139.24
        'port': 0x4444,
    },
    'np04-wib-503-d1': {
        'mac': 0x80d336005255,
        'ip': 0x0a498b19, # 10.73.139.24
        'port': 0x4444,
    },


    ### WIB 504
    'np04-wib-504-d0': {
        'mac': 0x80d336005256,
        'ip': 0x0a498b18, # 10.73.139.34
        'port': 0x4444,
    },
    'np04-wib-504-d1': {
        'mac': 0x80d336005257,
        'ip': 0x0a498b19, # 10.73.139.35
        'port': 0x4444,
    },

    ### WIB 505
    'np04-wib-505-d0': {
        'mac': 0x80d336005258,
        'ip': 0x0a498b1c, # 10.73.139.28
        'port': 0x4444,
    },
    'np04-wib-505-d1': {
        'mac': 0x80d336005259,
        'ip': 0x0a498b1d, # 10.73.139.29
        'port': 0x4444,
    }
}


ctrl_hosts = {
    'np04-zcu-001' : 'hermes_zcu_v0.9.1_b0',
    'np04-wib-501' : 'hermes_wib_v0.9.1_b0',
    'np04-wib-502' : 'hermes_wib_v0.9.1_b0',
    'np04-wib-503' : 'hermes_wib_v0.9.1_b0',
    'np04-wib-504' : 'hermes_wib_v0.9.1_b0',
    'np04-wib-505' : 'hermes_wib_v0.9.1_b0',
}
port = 5556

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
def cli(ctx, ctrl_id):
    obj = CrappyObj


    cm  = uhal.ConnectionManager('file://${CRAPPYZCU_SHARE}/config/c.xml')
    hw = cm.getDevice(ctrl_id)

    # Identify board
    is_zcu = hw.getNodes('tx.info')
    is_wib = hw.getNodes('info')

    if is_zcu:
        tx_mux = hw.getNode('tx')
    elif is_wib:
        tx_mux = hw.getNode()
    else:
        raise ValueError(f"{ctrl_id} is neither a zcu nor a wib")

    obj.hermes = HermesController(tx_mux)

    ctx.obj = obj

@cli.command()
def addrbook():

    t = Table(title="Control hosts")
    t.add_column('name')
    t.add_column('addrtable', style='green')
    for h,a in ctrl_hosts.items():
        t.add_row(h, a)
    print(t)

    t = Table(title="Receivers")
    t.add_column('name')
    t.add_column('mac', style='green')
    t.add_column('ip', style='blue')
    t.add_column('port', style='blue')
    for h,d in rx_endpoints.items():
        t.add_row(h, f"0x{d['mac']:012x}", f"0x{d['ip']:08x}", str(d['port']))
    print(t)

    t = Table(title="Transmitters")
    t.add_column('name')
    t.add_column('mac', style='green')
    t.add_column('ip', style='blue')
    t.add_column('port', style='blue')
    for h,d in tx_endpoints.items():
        t.add_row(h, f"0x{d['mac']:012x}", f"0x{d['ip']:08x}", str(d['port']))
    print(t)

@cli.command()
@click.option('--en/--dis', 'enable', default=None)
@click.option('--buf-en/--buf-dis', 'buf_en', default=None)
@click.option('--tx-en/--tx-dis', 'tx_en', default=None)
@click.option('-l', '--link', type=int, default=0)
@click.pass_obj
def enable(obj, enable, buf_en, tx_en, link):

    hrms = obj.hermes

    n_mgt = hrms.n_mgt

    if link >= n_mgt:
        raise ValueError(f"MGT {link} not instantiated")
    
    hrms.sel_tx_mux(link)

    print()
    if enable is not None:
        print(f"- {'Enabling' if enable else 'Disabling'} 'mux'")
        hrms.get_node('mux.csr.ctrl.en').write(enable)

    if buf_en is not None:
        print(f"- {'Enabling' if buf_en else 'Disabling'} 'input buffers'")
        hrms.get_node('mux.csr.ctrl.en_buf').write(buf_en)

    if tx_en is not None:
        print(f"- {'Enabling' if tx_en else 'Disabling'} 'tx block'")
        hrms.get_node('mux.csr.ctrl.en_buf').write(tx_en)
    print()
    
    hrms.dispatch()


    top_ctrl = dump_sub_regs(hrms.get_node('mux.csr.ctrl'))

    print(
        dict_to_table(top_ctrl, title=f'Link {link} ctrls', show_header=False), 
    )


@cli.command("mux-config")
@click.argument('detid', type=int)
@click.argument('crate', type=int)
@click.argument('slot', type=int)
@click.option('-l', '--link', type=int, default=0)
@click.pass_obj
def mux_config(obj, detid, crate, slot, link):
    """Comfigure the UDP blocks """

    hrms = obj.hermes

    if link >= hrms.n_mgt:
        raise ValueError(f"Link {link} not instantiated")
    
    hrms.sel_tx_mux(link)

    hrms.get_node('mux.mux.ctrl.detid').write(detid)
    hrms.get_node('mux.mux.ctrl.crate').write(crate)
    hrms.get_node('mux.mux.ctrl.slot').write(slot)
    
    mux_ctrl = dump_sub_regs(hrms.get_node('mux.mux.ctrl'))

    print(
        dict_to_table(mux_ctrl, title=f'Link {link} mux cfg', show_header=False), 
    )


@cli.command("udp-config")
@click.argument('src_id', type=click.Choice(tx_endpoints.keys()))
@click.argument('dst_id', type=click.Choice(rx_endpoints.keys()))
@click.option('-l', '--link', type=int, default=0)
@click.pass_obj
def udp_config(obj, src_id, dst_id, link):
    """Comfigure the UDP blocks """

    filter_control = 0x07400307
    hrms = obj.hermes

    if link >= hrms.n_mgt:
        raise ValueError(f"Link {link} not instantiated")


    # hw = obj.hw

    dst = rx_endpoints[dst_id]
    src = tx_endpoints[src_id]

    udp_core_ctrl = f'udp.udp_core_{link}.udp_core_control.nz_rst_ctrl'

    hrms.get_node(f'{udp_core_ctrl}.filter_control').write(filter_control)

    # Our IP address = 10.73.139.23
    print(f"Our ip address: {socket.inet_ntoa(src['ip'].to_bytes(4, 'big'))}")
    hrms.get_node(f'{udp_core_ctrl}.src_ip_addr').write(src['ip']) 

    # Their IP address = 10.73.139.23
    print(f"Their ip address: {socket.inet_ntoa(dst['ip'].to_bytes(4, 'big'))}")
    # hw.write(f'{udp_core_ctrl}.dst_ip_addr', dst['ip']) 
    hrms.get_node(f'{udp_core_ctrl}.dst_ip_addr').write(dst['ip']) 
    
    # Our MAC address
    # Dest MAC address
    print(f"Our mac address: 0x{src['mac']:012x}")
    # hw.write(f'{udp_core_ctrl}.src_mac_addr_lower', src['mac'] & 0xffffffff) 
    # hw.write(f'{udp_core_ctrl}.src_mac_addr_upper', (src['mac'] >> 32) & 0xffff) 
    hrms.get_node(f'{udp_core_ctrl}.src_mac_addr_lower').write(src['mac'] & 0xffffffff) 
    hrms.get_node(f'{udp_core_ctrl}.src_mac_addr_upper').write((src['mac'] >> 32) & 0xffff) 

    # Dest MAC address
    print(f"Their mac address: 0x{dst['mac']:012x}")
    # hw.write(f'{udp_core_ctrl}.dst_mac_addr_lower', dst['mac'] & 0xffffffff) 
    # hw.write(f'{udp_core_ctrl}.dst_mac_addr_upper', (dst['mac'] >> 32) & 0xffff) 
    hrms.get_node(f'{udp_core_ctrl}.dst_mac_addr_lower').write(dst['mac'] & 0xffffffff) 
    hrms.get_node(f'{udp_core_ctrl}.dst_mac_addr_upper').write((dst['mac'] >> 32) & 0xffff) 

    # Ports
    hrms.get_node(f'{udp_core_ctrl}.udp_ports.src_port').write(src['port']) 
    hrms.get_node(f'{udp_core_ctrl}.udp_ports.dst_port').write(dst['port']) 

    hrms.dispatch()


@cli.command("zcu-src-config")
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


@cli.command("fakesrc-config")
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


@cli.command()
@click.pass_obj
@click.option('-l', '--links', 'sel_links', type=click.Choice(mgts_all), multiple=True, default=None)
@click.option('-s', '--seconds', type=int, default=0)
def stats(obj, sel_links, seconds):
    """Simple program that greets NAME for a total of COUNT times."""

    hrms = obj.hermes

    mgts = list(range(hrms.n_mgt))
    
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

    print(f"Sampling hermes counters for {seconds}s")
    hrms.sample_ctrs(seconds)

    info_data = dump_sub_regs(hrms.get_node('info'))
    print(dict_to_table(info_data, title='hermes info', show_header=False))

    # n_srcs_p_mgt = n_src//n_mgt

    for i in sel_links:
        print(f'---Tx Mux {i} Status---')

        hrms.sel_tx_mux(i)


        # cli control registers
        top_ctrl = dump_sub_regs(hrms.get_node('mux.csr.ctrl'))
        top_stat = dump_sub_regs(hrms.get_node('mux.csr.stat'))
        ctrl_mux = dump_sub_regs(hrms.get_node('mux.mux.ctrl'))
        stat_mux = dump_sub_regs(hrms.get_node('mux.mux.stat'))

        grid = Table.grid()
        grid.add_column("ctrl")
        grid.add_column("stat")
        grid.add_row(
            dict_to_table(top_ctrl, title='tx_mux ctrl', show_header=False), 
            dict_to_table(top_stat, title='tx mux stat', show_header=False),
            dict_to_table(ctrl_mux, title="mux ctrl", show_header=False),
            dict_to_table(stat_mux, title="mux stat", show_header=False),
        )
        print(grid)
        

        ctrl_udp = dump_sub_regs(hrms.get_node(f'udp.udp_core_{i}.udp_core_control.nz_rst_ctrl'))
        ctrl_flt_udp = dump_sub_regs(hrms.get_node(f'udp.udp_core_{i}.udp_core_control.nz_rst_ctrl.filter_control'))
        stat_udp = dump_sub_regs(hrms.get_node(f'udp.udp_core_{i}.udp_core_control.packet_counters'))


        ctrl_srcdst = {}
        ctrl_srcdst['src_ip'] = ctrl_udp['src_ip_addr']
        ctrl_srcdst['dst_ip'] = ctrl_udp['dst_ip_addr']
        ctrl_srcdst['src_mac'] = (ctrl_udp['src_mac_addr_upper.upper'] << 32) + ctrl_udp['src_mac_addr_lower']
        ctrl_srcdst['dst_mac'] = (ctrl_udp['dst_mac_addr_upper.upper'] << 32) + ctrl_udp['src_mac_addr_lower']
        ctrl_srcdst['src_port'] = ctrl_udp['udp_ports.src_port']
        ctrl_srcdst['dst_port'] = ctrl_udp['udp_ports.dst_port']

        grid = Table.grid()
        grid.add_column("ctrl")
        grid.add_column("stat")
        grid.add_row(
            # dict_to_table(ctrl_udp, title="udp ctrl", show_header=False),
            dict_to_table(ctrl_srcdst, title="udp src/dst", show_header=False),
            dict_to_table(ctrl_flt_udp, title="udp filter", show_header=False),
            dict_to_table(stat_udp, title="udp stat", show_header=False),
        )
        print(grid)

        ibuf_stats = {}

        src_ids = tuple(range(hrms.n_srcs_p_mgt))
        for j in src_ids:
            # hw.write('tx.mux.csr.ctrl.sel_buf',j)
            hrms.sel_tx_mux_buf(j)
            s =  dump_sub_regs(hrms.get_node('mux.buf'))
            s['blk_acc'] = (s['blk_acc_h']<<32)+s['blk_acc_l']
            s['blk_oflow'] = (s['blk_oflow_h']<<32)+s['blk_oflow_l']
            s['blk_rej'] = (s['blk_rej_h']<<32)+s['blk_rej_l']
            s['ts'] = (s['ts_h']<<32)+s['ts_l']
            s['vol'] = (s['vol_h']<<32)+s['vol_l']

            for k in tuple(s.keys()):
                for n in ('blk_acc_', 'blk_oflow_', 'blk_rej_', 'ts_', 'vol_'):
                    if k.startswith(n):
                        del s[k]

            for k in ('ctrl', 'stat', 'buf_mon'):
                del s[k]

                
            ibuf_stats[j] = s

        # Create the summary table
        t = Table()

        # Add 1 column for the reg name, and as many as the number of sources
        t.add_column('name')
        for j in src_ids:
            t.add_column(f'Buf {j}', style='green')

        # Unify the reg list (useless?)
        reg_names = set()
        for k,v in ibuf_stats.items():
            reg_names = reg_names.union(v.keys())
        
        for n in sorted(reg_names):
            t.add_row(n,*(hex(ibuf_stats[j][n]) for j in src_ids))
        print(t)
        

if __name__ == '__main__':
    FORMAT = "%(message)s"
    logging.basicConfig(
        level="INFO", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
    )
    cli()