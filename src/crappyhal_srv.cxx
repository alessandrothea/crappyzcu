#include <iostream>
#include <cstdlib>
#include <unistd.h>
#include <fcntl.h>
#include <stdint.h>
#include <sys/mman.h>
#include <set>
#include <algorithm>
#include <sstream>

#include <zmq.hpp>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

struct DevMemMappingError : public std::exception
{
	const char * what () const throw ()
    {
    	return "Failed to map /dev/mem to memory";
    }
};

uint32_t get_bitshift(uint32_t mask) {
    uint32_t m = mask;
    for( size_t s(0); s<32; ++s) {
        m = mask >> s;
        if ( m & 0x1 )
            return s;
    }

    return 32;
}

class CrappyHardware {
public:
    CrappyHardware(size_t base_addr, size_t addr_len) {
	    m_base_addr = base_addr;
        m_addr_len = addr_len;

        int r = mem_map();
        if ( r != 0 ) {
            throw DevMemMappingError();
        }
    }

    ~CrappyHardware() {
        mem_unmap();
    }



    uint32_t read_addr(uint32_t addr, uint32_t mask) {
        // if self.VERBOSE: print(hex(addr), hex(mask))

        uint32_t val = *(m_base_ptr+addr);
        if (mask == 0xffffffff)
            return val;

        uint32_t s = get_bitshift(mask);
        return ((val & mask) >> s);
    }

    void write_addr(uint32_t addr, uint32_t mask, uint32_t val) {
        if (mask == 0xffffffff) {
            *(m_base_ptr+addr) = val;
        } else {
            uint32_t s = get_bitshift(mask);
            uint32_t m = mask >> s;
            uint32_t reg_val = *(m_base_ptr+addr);

            *(m_base_ptr+addr) = (reg_val & ~mask) | ((val & m) << s);
        }
    }

private:

    int mem_map() {

	    m_dev_mem_fd=::open("/dev/mem",O_RDWR|O_SYNC);
	    if (m_dev_mem_fd < 1) 
            return -1;
            // throw DevMemMappingError();

	    size_t ptr = (size_t) mmap(NULL,m_addr_len*4,PROT_READ|PROT_WRITE,MAP_SHARED,m_dev_mem_fd,m_base_addr);
	    if (ptr == -1) 
            return -2;
            // throw DevMemMappingError();

        m_base_ptr = (uint32_t*)(ptr);
        return 0;
    }

    int mem_unmap() {
        munmap(m_base_ptr,m_addr_len*4);
        ::close(m_dev_mem_fd);
        return 0;
    }   

    int m_dev_mem_fd;
    size_t m_base_addr;
    size_t m_addr_len;
    uint32_t* m_base_ptr;

};


void json_reply(zmq::socket_t& socket, const json& data) {
    std::string reply_str = data.dump(); 

    zmq::message_t reply(reply_str.size());
    memcpy((void*)reply.data(), reply_str.c_str(), reply_str.size());

    // Send w/o waiting in case the client is not there any longer.    
    socket.send(reply, zmq::send_flags::none);
}

json json_receive(zmq::socket_t& socket) {

    zmq::message_t msg;
    auto r = socket.recv(msg,zmq::recv_flags::none);        
    std::string msg_str((char*)msg.data(), msg.size());
    // std::cout << "received message '" << msg_str << "'" << std::endl;
    return json::parse(msg_str);
}

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

    // uint64_t axi_base_addr = 0x80000000;
    uint64_t axi_base_addr = device_it->second;
    uint64_t axi_addr_width = 0x10000;

    std::cout << "CrappyHAL server starting"<< std::endl;
    std::cout << "- Base AXI address: 0x" << std::hex << axi_base_addr << std::endl;
    std::cout << "- IPBus address width (AXI space): 0x" << std::hex << axi_addr_width << std::endl;

    CrappyHardware hw(axi_base_addr, axi_addr_width);
    uint32_t v;
    v = hw.read_addr(0x0, 0xffffffff);
    std::cout << "" << std::hex << v << std::endl;

    zmq::context_t context;
    zmq::socket_t socket(context, ZMQ_REP);

    socket.bind("tcp://*:5556");

    for (int i = 0; ; i++) {

        json data;
        try {
            data = json_receive(socket);

        } catch ( std::exception &e ) {
            std::cerr << "Failed to deserialize command message to json " << e.what() << std::endl;
            json reply_data = { {"err", "InvalidJSONFormat"} };
            json_reply(socket, reply_data);
            continue;
        }

        std::set<std::string> keys;
        for (auto& [key, val] : data.items())
        {
            // std::cout << "key: " << key << ", value:" << val << '\n';
            keys.insert(key);
        }
        std::set<std::string> good_keys = {"cmd", "addr", "mask", "val"};
        if (!std::includes(good_keys.begin(), good_keys.end(), keys.begin(), keys.end())) {
            std::cerr << "Invalid message received" << std::endl;
            json reply_data = { {"err", "InvalidMessage"} };
            json_reply(socket, reply_data);
            continue;
        }

        std::string cmd = data["cmd"];
        uint32_t addr = data["addr"].get<uint32_t>();
        uint32_t mask = data["mask"].get<uint32_t>();

        if ( addr < 0 or addr > 0xffffffff ) {
            std::cerr << "Invalid address received" << std::endl;
            json_reply(socket, {{"err", "InvalidAddress"}});
            continue;

        }
        if ( mask < 0 or mask > 0xffffffff ) {
            std::cerr << "Invalid mask received" << std::endl;
            json_reply(socket, {{"err", "InvalidMask"}});
            continue;
        }

        if ( cmd == "read" ) {
            uint32_t val = hw.read_addr(addr, mask);
            std::cout << "Read 0x" << std::hex << val << " at 0x" << addr << " with mask 0x" << mask << std::endl;
            std::stringstream ss;
            ss << "0x" << std::hex << val;
            json_reply(socket, {{"read_val", ss.str()}} );
            continue;
        } else if ( cmd == "write" ) {
            uint32_t val = data["val"].get<uint32_t>();

            hw.write_addr(addr, mask, val);
            std::cout << "Write 0x" << std::hex << val << " at 0x" << addr << " with mask 0x" << mask << std::endl;
            json_reply(socket, {{"write_done", true}} );
            continue;

        } else {
            std::cerr << "Invalid command received" << std::endl;
            json_reply(socket, {{"error", "InvalidCommand"}} );
            continue;
        }

        json reply_data = {};
        json_reply(socket, reply_data);

    }
    return 0;

}