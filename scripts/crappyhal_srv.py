#!/usr/bin/env python
import zmq
import click
import json

import coloredlogs, logging
logger = logging.getLogger(__name__)

from crappyhal import CrappyRawHardware

@click.command()
@click.option('-p', '--port', type=int, default=5556)
def main(port):

    hw = CrappyRawHardware()

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:%s" % port)

    logger.info('Starting crappyhal server')
    while True:
        #  Wait for next request from client
        message = socket.recv()
        logger.debug(f"Received request: {message.decode()}")
        try:
            d = json.loads(message)
        except:
            logger.error(f"Failed to deserialize {message.decode(())} to json")
            socket.send(json.dumps({'error': 'InvalidJSONFormat'}).encode())
            continue

        if not set(d.keys()).issubset({'cmd', 'addr', 'mask', 'val'}):
            logger.error("Invalid message received")
            socket.send(json.dumps({'error': 'InvalidMessage'}).encode())
            continue
        
        cmd = d['cmd']
        addr = int(d['addr'], 0)
        mask = int(d['mask'], 0)
        val = int(d['val'], 0) if 'val' in d else None

        if addr < 0 or addr > 0xffffffff:
            logger.error("Invalid address received")
            socket.send(json.dumps({'err': 'InvalidAddress'}).encode())
            continue

        if mask < 0 or mask > 0xffffffff:
            logger.error("Invalid address received")
            socket.send(json.dumps({'err': 'InvalidAddress'}).encode())
            continue

        # if cmd not in ['read', 'write']:
        #     print("Invalid command received")
        #     socket.send(json.dumps({'error': 'InvalidCommand'}).encode())
        #     continue

        if cmd == 'read':
            v = hw.read_addr(addr, mask)
            logger.info(f"Read {hex(v)} at {hex(addr)} with mask {hex(mask)}")
            socket.send(json.dumps({'read_val': hex(v)}).encode())
            continue

        elif cmd == 'write':
            hw.write_addr(addr, mask, val)
            logger.info(f"Write {hex(val)} at {hex(addr)} with mask {hex(mask)}")
            socket.send(json.dumps({'write_done': True}).encode())
            continue

        else:
            print("Invalid command received")
            socket.send(json.dumps({'error': 'InvalidCommand'}).encode())
            continue   
        


if __name__ == '__main__':
    
    coloredlogs.install(level='INFO', logger=logger)

    main()