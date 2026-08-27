# System.py
 
# Local imports
from Emu.System.Dependencies import Teknikality
from Emu.System              import Vars
from Emu.Exceptions          import Exceptions
 
# Lib imports
import sys
import os
import time
import re
# Check valid OS (Windows)
if os.name != "nt":
    raise OSError("Windows-only program.")
import ctypes

def emu_warn(msg):
    sys_write_stdout(f"{Teknikality.colors.YELLOW}WARNING: {Teknikality.colors.BRIGHT_BLACK}{msg}{Teknikality.colors.RESET}")
 
def sys_write_stdout(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()
 

 
def error_window(error_message, error_code, error_title='Application Error'):
    u_type = 0x0 | 0x10
 
    ctypes.windll.user32.MessageBoxW(0, f"{error_message}\n\nError Code: {hex(error_code)}", error_title, u_type)
 
class DwordArray:
    """A helper object for 32-bit registers"""
    def __init__(self, slots):
        self.starting_slots     =       slots
        self.arr                =       [0] * slots
        self.max_index          =       len(self.arr) - 1 # minus 1 for zero-index
        self.mask               =       0xFFFFFFFF        # 32-bit integer limit
        self.size               =       len(self.arr)
 
    def write(self, val, arr=0):
 
        if not 0 <= arr <= self.max_index:
            raise Exceptions.InvalidRegister
       
        self.arr[arr] = (val & self.mask)
 
    def read(self, arr=0):
        if not 0 <= arr <= self.max_index:
            raise Exceptions.InvalidRegister
 
        return self.arr[arr]
 
    def clear(self):
        self.arr = [0] * self.starting_slots
 
    def increment(self, t=0, arr=0):
        if not 0 <= arr <= self.max_index:
            raise Exceptions.InvalidRegister
 
        current = self.read(arr=arr)
        current += 1 + t
 
        self.write(arr=arr, val=current)
 
    def decrement(self, t=0, arr=0):
        if not 0 <= arr <= self.max_index:
            raise Exceptions.InvalidRegister
 
        current = self.read(arr=arr)
        current -= 1 + t
 
        self.write(arr=arr, val=current)    
       
 
class registers:
 
    def __init__(self):
        self.regs32       = DwordArray(24) # 24 general-purpose 32-bit registers
        self.regs32_save  = DwordArray(24) # Register save slots for interrupts
        self.ip           = DwordArray(1)  # 32-bit instruction pointer
        self.flags        = {
            "EQ": 0,                       # Comparison was equal
            "HI": 0,                       # First register was higher
            "LO": 0,                       # First register was lower
            "IF": 0                        # Interrupt flag, 1=on, 0=off.
 
        }
        self.sp           = DwordArray(1)  # Stack initialized to 0x00000000

           
 
class memory:
    MEM_SIZE = 256 * 1024 * 1024
    MAX_ADDR = 0x0FFFFFFF
    class Map:
        """
        Class for resolving address regions in memory
        All formatted *[end, start]* in a **list**
        """
        IVT         = [0x00000000, 0x000000FF]         # Not really used anywhere since IVT indexing is done via bytes, which cannot physically go above 0xFF
        VIDEO       = [0x0B800000, 0x0B800FFF]         # Nice lil x86 throwback
       
    def __init__(self):
        self.Memory = bytearray(self.MEM_SIZE)
 
    # ----------------
    # Read operations
    # ----------------
 
    def read_byte(self, addr):
        if addr > self.MAX_ADDR:
            raise Exceptions.InvalidMemoryWrite
        return self.Memory[addr]
 
    def read_word(self, addr):
        if addr > self.MAX_ADDR:
            raise Exceptions.InvalidMemoryWrite        
        return (
            self.Memory[addr]
            | (self.Memory[addr + 1] << 8)
        )
 
    def read_dword(self, addr):
        if addr > self.MAX_ADDR:
            raise Exceptions.InvalidMemoryWrite        
        return (
            self.Memory[addr]
            | (self.Memory[addr + 1] << 8)
            | (self.Memory[addr + 2] << 16)
            | (self.Memory[addr + 3] << 24)
        )
 
    # -----------------
    # Write operations
    # -----------------
 
    def write_byte(self, addr, val):
        if addr > self.MAX_ADDR:
            raise Exceptions.InvalidMemoryWrite        
        self.Memory[addr] = val & 0xFF
 
    def write_word(self, addr, val):
        if addr > self.MAX_ADDR:
            raise Exceptions.InvalidMemoryWrite        
        self.Memory[addr]     = val & 0xFF
        self.Memory[addr + 1] = (val >> 8) & 0xFF
 
    def write_dword(self, addr, val):
        if addr > self.MAX_ADDR:
            raise Exceptions.InvalidMemoryWrite        
        self.Memory[addr]     = val & 0xFF
        self.Memory[addr + 1] = (val >> 8) & 0xFF
        self.Memory[addr + 2] = (val >> 16) & 0xFF
        self.Memory[addr + 3] = (val >> 24) & 0xFF

def format_hex_16(val):
    return f"{val:04x}"
 
def format_hex_8(val):
    return f"{val:02x}"
 
def format_hex_32(val):
    return f"{val:08x}"