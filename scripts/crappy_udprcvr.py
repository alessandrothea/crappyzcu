#!/usr/bin/env python
import socket
import devmem

UDP_IP = "10.73.138.70"
UDP_PORT = 50001
AXI_OFFSET = 0x80000000
AXI_LENGTH = 0x100000

IPB_MB_OFFSET=0x10000

mem = devmem.DevMem(AXI_OFFSET, AXI_LENGTH, "/dev/mem", 0)


sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP
sock.bind((UDP_IP, UDP_PORT))

while True:
    data, addr = sock.recvfrom(2048) # buffer size is 1024 bytes
    print(f"received message: {data} {addr}")

    u32_data = [int.from_bytes(data[4*i:4*(i+1)], byteorder='little', signed=False) for i in range(len(data)//4)]


    status =  mem.read(0, 4)
    num_buf = status[0]
    word_per_page = status[1]
    next_req_page = status[2]
    num_replies = status[3]

    print(f"Num buf       : {num_buf} {status[0]:08x}")
    print(f"Word per page : {word_per_page} {status[1]:08x}")
    print(f"Next page     : {next_req_page} {status[2]:08x}")
    print(f"Num replies   : {num_replies} {status[3]:08x}")

    next_req_base_addr = word_per_page*next_req_page
    print(len(u32_data), [hex(d) for d in u32_data])
    data_len = (IPB_MB_OFFSET | (len(u32_data)-1))
    print(f"Writing pkt len word {data_len:08x} at addr {next_req_base_addr:08x} (page {next_req_page})")
    mem.write(4*next_req_base_addr, [data_len])
    
    print(f"Writing pkt data at addr {next_req_base_addr+1:08x}")
    mem.write(4*(next_req_base_addr+1), u32_data)
    # for i,w in enumerate(u32_data):
        # print(f"Writing {i} word {w:08x} at addr {next_req_base_addr+1+i:08x}")
        # mem.write(4*(next_req_base_addr+1+i), [w])



    reply_page = None
    while True:
        b = mem.read(0, 4)
        new_num_replies = b[3]
        if new_num_replies != num_replies:
            print(f"Old replies: {num_replies}, new replies {new_num_replies}")
            reply_page = new_num_replies
            break

    for p in range(num_buf):
        paddr = 4+word_per_page*p
        print(f"  DEBUG: reading reply size at addr {paddr:08x} (page {p})")
        r = mem.read(4*paddr, 16)
        for w in r:
            print(f"{    w:08x}")
        rs = r[0] & ~IPB_MB_OFFSET
        print(f"  DEBUG: Reply size {rs} (reg {r[0]:08x})")


    next_rep_base_addr = 4+word_per_page*next_req_page
    print(f"Reading reply size at addr {next_rep_base_addr:08x} (page {next_req_page})")
    repl_size_reg = mem.read(4*next_rep_base_addr, 1)
    repl_size = (repl_size_reg[0] & ~IPB_MB_OFFSET)+1
    print(f"Reply size {repl_size} (reg {repl_size_reg[0]:08x})")
    repl = mem.read(4*(next_rep_base_addr+1), repl_size)

    b=b''
    for v in repl:
        print(f"{v:08x}")
        b +=  v.to_bytes(4, byteorder='little', signed=False)


    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    #Set a timeout value of 1 second
    clientSocket.settimeout(1)

    # #Ping to server
    # message = 'test'

    # addr = ("127.0.0.1", 12000)
    print(b)

    clientSocket.sendto(b, addr)


