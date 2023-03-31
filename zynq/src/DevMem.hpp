#ifndef __DEVMEM_HPP__
#define __DEVMEM_HPP__

#include <iostream>
#include <cstdlib>
#include <unistd.h>
#include <fcntl.h>
#include <stdint.h>
#include <sys/mman.h>
#include <set>
#include <algorithm>
#include <sstream>


namespace devmem {

struct DevMemMappingError : public std::exception
{
	const char * what () const throw ()
    {
    	return "Failed to map /dev/mem to memory";
    }
};

class DevMem {
public:
    DevMem(size_t base_addr, size_t addr_len) {
	    m_base_addr = base_addr;
        m_addr_len = addr_len;

        int r = mem_map();
        if ( r != 0 ) {
            throw DevMemMappingError();
        }
    }

    ~DevMem() {
        mem_unmap();
    }

    uint32_t read(uint32_t addr) {
        uint32_t val = *(m_base_ptr+addr);
        return val;
    }

    void write(uint32_t addr, uint32_t val) {
        *(m_base_ptr+addr) = val;
    }

    std::vector<uint32_t> read_block(uint32_t addr, size_t size) {
        // This doesn't work
        // std::vector<uint32_t> block(m_base_ptr+addr, m_base_ptr+addr+size);

        // But a for loop does?
        std::vector<uint32_t> block(size);
        for( size_t i(0); i<size; ++i) {
            block[i] = *(m_base_ptr+addr+i);
        }
        return block;

    }

    void write_block(uint32_t addr, const std::vector<uint32_t>& block) {
        // This doesn't work
        // ::memcpy((char*)(m_base_ptr+addr), block.data(), block.size()*sizeof(uint32_t));
        
        // But a for loop does?
        for( size_t i(0); i<block.size(); ++i) {
            *(m_base_ptr+addr+i) = block[i];
        }
    }

private:

    int mem_map() {

	    m_dev_mem_fd=::open("/dev/mem",O_RDWR|O_SYNC);
	    if (m_dev_mem_fd < 1) 
            return -1;
            // throw DevMemMappingError();

	    size_t ptr = (size_t) mmap(NULL, m_addr_len*4, PROT_READ|PROT_WRITE, MAP_SHARED, m_dev_mem_fd, m_base_addr);
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

}
#endif 