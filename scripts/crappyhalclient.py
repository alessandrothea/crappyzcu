#!/usr/bin/env python

import zmq
import sys
import json
import rich
import logging
import re
import uhal
import collections

uhal.setLogLevelTo(uhal.LogLevel.WARNING)

class CrappyRawHardwareClient:

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.context = None
        self.socket = None

    def __del__(self):
        self.disconnect()
    
    def connect(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect (f"tcp://{self.host}:{self.port}")
    
    def disconnect(self):
        if self.socket:
            self.socket.disconnect(f"tcp://{self.host}:{self.port}")


    def read_addr(self, addr, mask):

        req = {'cmd': 'read', 'addr': hex(addr), 'mask': hex(mask)}
        self.socket.send(json.dumps(req).encode())
        message = self.socket.recv()
        rpl = json.loads(message)
        # print(f"Received reply {req} [{rpl}]")
        return int(rpl['read_val'], 0)


    def write_addr(self, addr, mask, val):
        req = {'cmd': 'write', 'addr': hex(addr), 'mask': hex(mask), 'val': hex(val)}
        self.socket.send(json.dumps(req).encode())
        message = self.socket.recv()
        # print(f"Received reply {req} [{message.decode('utf-8')}]")


class CrappyHardwareClient(CrappyRawHardwareClient):

    def __init__(self, host, port, top_addrfile):
        CrappyRawHardwareClient.__init__(self, host, port)

        # with open(top_addrfile, 'r') as f:
            # self._addrtab = json.load(f)

        # Create a dummy device to parse the address table
        hw = uhal.getDevice('dummy', 'ipbusudp-2.0://127.0.0.1:50001', f'file://{top_addrfile}')
        nodes = hw.getNodes()

        flat_regmap = collections.OrderedDict()
        for n in nodes:
            flat_regmap[n] = {'addr':hex(hw.getNode(n).getAddress()), 'mask':hex(hw.getNode(n).getMask()) }   
        self._addrtab = flat_regmap

    @property
    def addrtab(self):

        return self._addrtab

    def get_regs(self, regex):
        exp = re.compile(regex)
        
        return [ name for name in self._addrtab if exp.match(name) ]


    def read(self, name):
        if not name in self._addrtab:
            raise ValueError('Unknown register '+name)
        
        addr = int(self._addrtab[name]['addr'],0)
        mask = int(self._addrtab[name]['mask'],0)

        logging.debug(f"{hex(addr)}, {hex(mask)}")

        return self.read_addr(addr, mask)



    def write(self, name, val):
        if not name in self._addrtab:
            raise ValueError('Unknown register '+name)

        addr = int(self._addrtab[name]['addr'],0)
        mask = int(self._addrtab[name]['mask'],0)

        return self.write_addr(addr, mask, val)



# @click.command()
# def main():

#     port = "5556"
# # if len(sys.argv) > 1:
# #     port =  sys.argv[1]
# #     int(port)

# # if len(sys.argv) > 2:
# #     port1 =  sys.argv[2]
# #     int(port1)
#     # context = zmq.Context()
#     # print("Connecting to server...")
#     # socket = context.socket(zmq.REQ)
#     # socket.connect (f"tcp://np04-zcu-001:{port}")


#     # req = {'cmd': 'read', 'addr': '0x2', 'mask': '0xffffffff'}

#     # #  Do 10 requests, waiting each time for a response
#     # for request in range (1,10):
#     #     print(f"Sending request {request}...")
#     #     socket.send (json.dumps(req).encode())
#     #     #  Get the reply.
#     #     message = socket.recv()
#     #     print(f"Received reply {request} [{message.decode('utf-8')}]")

#     hw =  CrappyRawHardwareClient('np04-zcu-001', port)
#     hw.connect()

#     v = hw.read_addr(0x2, 0xffffffff)
#     print(v)
#     v = hw.write_addr(0x0, 0xffffffff, 0)



# if __name__ == '__main__':
#     FORMAT = "%(message)s"
#     logging.basicConfig(
#         level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
#     )

#     main()
