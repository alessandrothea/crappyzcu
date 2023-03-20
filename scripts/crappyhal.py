import json
import devmem
import time
import sys
import devmem

class CrappyRawHardware : 

    def __init__(self, verb=False):

        self.AXI_OFFSET = 0x80000000
        self.AXI_LENGTH = 0x100000
        self.VERBOSE = verb
        self.mem = devmem.DevMem(self.AXI_OFFSET, self.AXI_LENGTH, "/dev/mem", 0)

    def _wreg(self, a, d):
        self.mem.write(a*4, d)

    def _rreg(self, a, n):
        b = self.mem.read(a*4, n)
        return b.data


    def get_shift_and_mask(self, mask):
        for s in range(32):
            m = (mask >> s)
            if m & 1:
                break
        return s, m


    def read_addr(self, addr, mask):
        if self.VERBOSE: print(hex(addr), hex(mask))

        val =  self._rreg(addr, 1)[0]

        if mask == 0xffffffff:
            return val
        else:
            s, m = self.get_shift_and_mask(mask)

        return ((val & mask) >> s)


    def write_addr(self, addr, mask, val):
        if mask == 0xffffffff:
            self._wreg(addr, [val])
        else:
            # Read-modify-write
            s, m = self.get_shift_and_mask(mask)

            reg_val = self._rreg(addr, 1)[0]
            
            reg_new = (reg_val & ~mask) | ((val & m) << s)
            self._wreg(addr, [reg_new]) 


class CrappyHardware(CrappyRawHardware):
    def __init__(self, addrtab, verb=False):
        CrappyRawHardware.__init__(self, verb)

        with open(addrtab, 'r') as f:
            self._addrtab = json.load(f)


    AXI_OFFSET = 0x80000000
    VERBOSE = False

    @property
    def addrtab(self):
        return self._addrtab

    def read(self, name):
        if not name in self._addrtab:
            raise ValueError('Unknown register '+name)
        
        addr = int(self._addrtab[name]['addr'],0)
        mask = int(self._addrtab[name]['mask'],0)

        if self.VERBOSE: print(hex(addr), hex(mask))

        return self.read_addr(addr, mask)



    def write(self, name, val):
        if not name in self._addrtab:
            raise ValueError('Unknown register '+name)

        addr = int(self._addrtab[name]['addr'],0)
        mask = int(self._addrtab[name]['mask'],0)

        return self.write_addr(addr, mask, val)



