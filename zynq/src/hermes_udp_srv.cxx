
#include "UDPSocket.hpp"
#include "DevMem.hpp"
#include "argparse.h"
#include <iostream>
#include <iomanip>
#include <map>
#include <chrono>
#include <thread>

using namespace std::chrono_literals;

static constexpr uint16_t UDP_PORT = 50001;

static constexpr uint32_t HEADER_LENGTH=0x1;
static constexpr uint64_t AXI_ADDR_LENGTH = 0x10000;

void print_ipbus_if_status(const std::vector<uint32_t>& status ) {
    std::ios_base::fmtflags f( std::cout.flags() );

    std::cout << "   * num_bufs     : " << status[0] << std::endl;
    std::cout << "   * word_per_page: " << status[1] << std::endl;
    std::cout << "   * next_req_page: " << status[2] << std::endl;
    std::cout << "   * num_replies  : " << status[3] << std::endl;

    std::cout.flags( f );

}


void print_ipbus_packet(const std::vector<uint32_t>& packet ) {
    std::ios_base::fmtflags f( std::cout.flags() );

    for( uint32_t x : packet ) { 
        std::cout << "   0x" << std::hex << std::setw(8) << std::setfill('0') << x << std::endl;
    }

    std::cout.flags( f );

}

int main(int argc, const char* argv[]) {


    argparse::ArgumentParser parser(argv[0], "Hermes udp ipbus bridge server");
    parser.add_argument("-d", "--device", "device type", true);
    parser.add_argument("-v", "--verbose", "verbosity level", false);
    parser.add_argument("-c", "--check-replies-count", "Check Replies count", false);
    parser.enable_help();

    auto err = parser.parse(argc, argv);
    if (err) {
        parser.print_help();
        std::cout << err << std::endl;
        return -1;
    }
    
    if (parser.exists("help")) {
        parser.print_help();
        return 0;
    }

    std::string device = parser.get<std::string>("device");
    bool verbose = parser.exists("verbose");
    bool check_replies_count = true;
    if (parser.exists("check-replies-count")) {
        check_replies_count = parser.get<bool>("check-replies-count");
    }

    std::cout << "device "  << device << std::endl;
    std::cout << "verbose " << verbose << std::endl;
    std::cout << "check " << check_replies_count << std::endl;

    // std::string device = argv[1];
    std::map<std::string, uint64_t> device_baseaddress_map = {
        {"zcu102", 0x80000000},
        {"wib", 0xa0020000},
    };
    

    std::cout << "Device type: " << device << std::endl;

    auto device_it = device_baseaddress_map.find(device);
    if ( device_it == device_baseaddress_map.end() ) {
        std::cerr << "ERROR: device " << device << " unknown."<< std::endl;
        exit(-1);
    }

    uint64_t axi_base_addr = device_it->second;

    std::cout << " - Mapping memory device at offset " << (void*)axi_base_addr << std::endl;
    devmem::DevMem mem(axi_base_addr, AXI_ADDR_LENGTH);
    std::cout << " - Mapping successful" << std::endl;

    std::cout << " - IPBus interface status" << std::endl;
    auto s = mem.read_block(0,4);
    print_ipbus_if_status(s);

    std::cout << " - Creating receiver at " << UDP_PORT << std::endl;
	UDPSocket srv;
	srv.open();
	srv.bind(UDP_PORT);
    std::cout << " - Receiver successfully bound" << std::endl;


    size_t req_count(0);
    size_t rpl_count(0);
    size_t to_count(0);
    while(true) {


        UDPSocket::IPv4 ipaddr; 
        std::string req_msg;
        try {
            srv.recv(req_msg, ipaddr);
            ++req_count;
        } catch (udp::RecvError& e) {
            std::cerr << "Error while receiving data" << std::endl;
            continue;
        }

        std::vector<uint32_t> data_uint32(req_msg.size()/sizeof(uint32_t));
        ::memcpy(data_uint32.data(), req_msg.data(), req_msg.size());
        
        if (verbose) {
            std::cout << "Received incoming ipbus packet:" << std::endl;
            print_ipbus_packet(data_uint32);
        }

        // Read ipbus interface status
        auto status = mem.read_block(0,4);

        if ( verbose ) {
            print_ipbus_if_status(status);
        }

        uint32_t num_buf = status[0];
        uint32_t word_per_page = status[1];
        uint32_t next_req_page = status[2];
        uint32_t num_replies = status[3];


        // Next address page
        uint32_t next_req_base_addr = word_per_page * next_req_page;

        // Prepare header word
        uint32_t pyld_size = data_uint32.size() - 1;
        uint32_t hdr_size = HEADER_LENGTH;
        uint32_t req_hdr_word = (hdr_size << 16 ) | pyld_size;

        mem.write(next_req_base_addr, req_hdr_word);
        mem.write_block(next_req_base_addr+1, data_uint32);

        std::chrono::time_point start = std::chrono::steady_clock::now();
        uint64_t wait_counts = 0;
        // Poll status registers waiting for a reply
        try {
            while(true) {
                auto status = mem.read_block(0,4);

                if ( verbose ) {
                    print_ipbus_if_status(status);
                }

                uint32_t new_num_replies = status[3];
                if (new_num_replies != num_replies or !check_replies_count) {
                    break;
                }

                if(std::chrono::steady_clock::now() - start > std::chrono::seconds(1)) 
                    throw std::runtime_error("Timed out while waiting for ipbus interface response");

                ++wait_counts;
                std::this_thread::sleep_for(1ms);

            }
        } catch ( std::runtime_error &e ) {
            std::cerr << "Error: timeout while retrieving reply form ipbus transactor" << std::endl;
            ++to_count;
            break;
        }

         
        // Calculate base address for reply packet
        uint32_t next_rep_base_addr = 4 + word_per_page * next_req_page;

        // Read the reply size word
        uint32_t rep_hdr_word = mem.read(next_rep_base_addr);
        // uint32_t rep_size = (rep_hdr_word & ~HEADER_LENGTH) + 1;
        uint32_t rep_size = ((rep_hdr_word >> 16) & 0xffff) + (rep_hdr_word & 0xffff);

        // Read the reply
        auto rep_data = mem.read_block(next_rep_base_addr+1, rep_size);

        // Prepare reply message
        std::string rep_msg(rep_data.size()*sizeof(uint32_t), ' ');
        ::memcpy(rep_msg.data(), rep_data.data(), rep_msg.length());
        ++rpl_count;

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