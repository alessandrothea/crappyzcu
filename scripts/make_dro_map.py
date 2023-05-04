#!/usr/bin/env python

import re
import json
from rich import print
import daqconf.detreadoutmap as dromap

from crappyzcu.tx_endpoints import tx_endpoints
from crappyzcu.rx_endpoints import rx_endpoints

m = dromap.DetReadoutMapService()

rx_host = 'np02-srv-002'
det_id = 3
crate_id = 4
iface = 0

rx_props = rx_endpoints[f'{rx_host}-100G']
rx_mac = ':'.join([f"{s:02x}" for s in rx_props['mac'].to_bytes(6,'big')])



rx = re.compile(r"np04-wib-(\d)0(\d)-d(\d)")


for name, tx_props in tx_endpoints.items():
    ma = rx.match(name)
    if not ma:
        continue
    c, s, l = ma.groups()
    if int(c) != crate_id:
        continue

    
    for i in range(4):
        strm_id = int(l)*64+i

        src_id = max(m.get())+1 if m.get() else 0

        # print(f"Adding {src_id}")
        tx_mac = ':'.join([f"{s:02x}" for s in tx_props['mac'].to_bytes(6,'big')])
        # print(tx_mac)
            
        m.add_srcid(
            src_id,
            dromap.GeoID(det_id, c, s, strm_id), 
            'eth',
            protocol="udp",
            mode="fix_rate",
            
            rx_iface=iface,
            rx_host=rx_host,
            rx_mac=rx_mac,
            rx_ip=rx_props['ip'],

            tx_host=name,
            tx_mac=tx_mac,
            tx_ip=tx_props['ip'],

        )

print(m.as_table())
outpath = f'apa{crate_id}_detreadout.json'
with open(outpath,"w") as f:
    json.dump(m.as_json(), f, indent=4)
print(f"Map saved to '{outpath}'")

import IPython
IPython.embed(colors="neutral")