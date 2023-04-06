
#include "UDPSocket.hpp"
#include "DevMem.hpp"
#include <iostream>
#include <iomanip>
#include <map>


// UDP_IP = "10.73.138.70"
static constexpr uint16_t UDP_PORT = 50001;
// static constexpr size_t AXI_OFFSET = 0x80000000;
// static constexpr size_t AXI_LENGTH = 0x100000;

static constexpr uint32_t HEADER_FLAG=0x10000;

// mem = devmem.DevMem(AXI_OFFSET, AXI_LENGTH, "/dev/mem", 0)

int main(int argc, char* argv[]) {

    if ( argc != 2 ) {
        std::cerr << "ERROR: 1 argument expected, " << argc << ", found."<< std::endl;
        std::cout << "Usage: " << argv[0] << " {wib,zcu102}" << std::endl;
        exit(1);
    }

    std::string device = argv[1];
    std::map<std::string, uint64_t> device_address_map = {
        {"zcu102", 0x80000000},
        {"wib", 0xa0020000},
    };
    

    std::cout << device << std::endl;

    auto device_it = device_address_map.find(device);
    if ( device_it == device_address_map.end() ) {
        std::cerr << "ERROR: device " << device << " unknown."<< std::endl;
        exit(-1);
    }

    uint64_t axi_base_addr = device_it->second;
    uint64_t axi_addr_length = 0x10000;

    std::cout << " - Mapping memory device at offset " << (void*)axi_base_addr << std::endl;
    devmem::DevMem mem(axi_base_addr, axi_addr_length);
    std::cout << " - Mapping successful" << std::endl;

    std::cout << " - IPBus interface status" << std::endl;
    auto s = mem.read_block(0,4);
    for( uint32_t v : s ) { 
        std::cout << "   " << v << std::endl;
    }
    // static constexpr uint16_t port = 50001;


    std::cout << " - Creating receiver at " << UDP_PORT << std::endl;
	UDPSocket srv;
	srv.open();
	srv.bind(UDP_PORT);
    std::cout << " - Receiver successfully bound" << std::endl;

    while(true) {


        UDPSocket::IPv4 ipaddr; 
        std::string req_msg;
        try {
            srv.recv(req_msg, ipaddr);
        } catch (udp::RecvError& e) {
            std::cerr << "Error while receiving data" << std::endl;
            continue;
        }

        std::vector<uint32_t> data_uint32(req_msg.size()/sizeof(uint32_t));
        ::memcpy(data_uint32.data(), req_msg.data(), req_msg.size());
        
        // std::cout << "Received incoming ipbus packet:" << std::endl;
        // for( uint32_t x : data_uint32 ) { 
        //     std::cout << "   0x" << std::hex << std::setw(8) << std::setfill('0') << x << std::endl;
        // }

        // Read ipbus interface status
        auto status = mem.read_block(0,4);

        uint32_t num_buf = status[0];
        uint32_t word_per_page = status[1];
        uint32_t next_req_page = status[2];
        uint32_t num_replies = status[3];


        // Next address page
        uint32_t next_req_base_addr = word_per_page * next_req_page;

        // Prepare header word
        uint32_t req_hdr_word = (HEADER_FLAG | (data_uint32.size() - 1));
        mem.write(next_req_base_addr, req_hdr_word);
        mem.write_block(next_req_base_addr+1, data_uint32);

        // Poll status registers waiting for a reply
        while(true) {
            auto status = mem.read_block(0,4);

            uint32_t new_num_replies = status[3];
            if (new_num_replies != num_replies) {
                break;
            }
        }

         
        // Calculate base address for reply packet
        uint32_t next_rep_base_addr = 4 + word_per_page * next_req_page;

        // Read the reply size word
        uint32_t rep_hdr_word = mem.read(next_rep_base_addr);
        uint32_t rep_size = (rep_hdr_word & ~HEADER_FLAG) + 1;

        // Read the reply
        auto rep_data = mem.read_block(next_rep_base_addr+1, rep_size);

        // Prepare reply message
        std::string rep_msg(rep_data.size()*sizeof(uint32_t), ' ');
        ::memcpy(rep_msg.data(), rep_data.data(), rep_msg.length());

        // Send reply
        UDPSocket rplr;
        rplr.open();
        rplr.send(rep_msg, ipaddr);
        rplr.close();

    }


    // UDPSocket::IPv4 ipaddr; 
    // std::string data;
    // try {
    //     srv.recv(data, ipaddr);
    // } catch (udp::RecvError& e) {

    // }

    // std::string response = "aaa";
    // rplr.send(response, ipaddr);


    // std::cout << "toc tpc" << std::endl;
    // std::cout << "Sender: " << ipaddr.to_string() << std::endl;
    // std::cout << "RCvdc data: " << data.size() << std::endl;

    srv.close();
}