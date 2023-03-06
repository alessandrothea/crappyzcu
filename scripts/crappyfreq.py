#!/usr/bin/env python
import time
import os
import click
from rich import print
from rich.table import Table
from rich.progress import track

from crappyhalclient import CrappyHardwareClient

host = 'np04-zcu-001'
port = 5556
# addrtab = 'zcu_top.flat_regmap.json'
addrtab = os.path.join(os.environ['CRAPPYZCU_SHARE'], 'config', 'hermes_zcu_mark3', 'zcu_top.xml')

@click.command()
def main():
    """Simple frequency measurement"""
    hw = CrappyHardwareClient(host, port, addrtab)
    hw.connect()
    clk_chans = range(4)


    t = Table()
    t.add_column('channel')
    t.add_column('Freq.', style='green')
    t.add_column('Counts.', style='cyan')

    for c in track(clk_chans, description="Measuring"):
        # print(f'Measuring channel {c}')
        hw.write('tx.udp.freq.ctrl.chan_sel', c)
        while(True):
            v = hw.read('tx.udp.freq.freq.valid')
            if v:
                break
            time.sleep(1/1000)
        cnt = hw.read('tx.udp.freq.freq.count')


        f = (cnt*64)/((2**24)/(75e6))
        # print(f"   Freq : {f/1e6:.5f} MHz [Counts {cnt} {hex(cnt)}]")
        t.add_row(str(c),f"{f/1e6:.5f} MHz",f"{cnt} [{hex(cnt)}]")
    print(t)


    print('Done')


if __name__ == '__main__':
    main()