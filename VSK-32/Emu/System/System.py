# System.py

# Local imports
from Emu.System.Dependencies import Teknikality

# Lib imports
import ctypes
import sys
import os
import time


def emu_warn(msg):
    sys_write_stdout(f"{Teknikality.colors.YELLOW}WARNING: {Teknikality.colors.BRIGHT_BLACK}{msg}{Teknikality.colors.RESET}")

def sys_write_stdout(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()

def VMError(py_code_class, cmsg, emsg, ecode):
    """Arg order: python error, console message, GUI error message, error code"""

    error_window(emsg, ecode)

    raise py_code_class(cmsg)

def error_window(error_message, error_code):
    u_type = 0x0 | 0x10

    ctypes.windll.user32.MessageBoxW(0, f"{error_message}\n\nError Code: {hex(error_code)}\nSee more in the emulator log terminal.", 'Application Error', u_type)

class DwordArray:
    """A helper object for 32-bit registers"""
    def __init__(self, slots):
        self.starting_slots     =       slots
        self.arr                =       [0] * slots
        self.max_index          =       len(self.arr) - 1 # minus 1 for zero-index
        self.mask               =       0xFFFFFFFF        # 32-bit integer limit
        self.size               =       len(self.arr)

    def write(self, val, arr=0):
        if val < 0:
            VMError(ValueError,
                    f"ERROR | Negative value passed to dwordarray.write() | Raised from -> write({val}, {arr})",
                    f"Operation not allowed: Attempted negative number write to unsigned integer",
                    0xAA
                    )

        if not 0 <= arr <= self.max_index:
            VMError(IndexError, 
                    f"ERROR | 32-bit register array index out of bounds: r{arr} | Raised from -> write({val}, {arr})",
                    f"Attempted WRITE to invalid register: {arr}",
                    0x10
                    )

        if val > self.mask:
            emu_warn(f"Integer overflow (register r{arr}): overflowed to 0x{format_hex_32(val & self.mask)}")
        
        self.arr[arr] = (val & self.mask)

    def read(self, arr=0):
        if not 0 <= arr <= self.max_index:
           VMError(IndexError, 
                  f"ERROR | 32-bit register array index out of bounds: r{arr} | Raised from -> read({arr})",
                  f"Attempted READ from invalid register: {arr}",
                  0x10
                  )

        return self.arr[arr]

    def clear(self):
        self.arr = [0] * self.starting_slots

    def increment(self, t=0, arr=0):
        if not 0 <= arr <= self.max_index:
            VMError(IndexError, 
                    f"ERROR | 32-bit register array index out of bounds: r{arr} | Raised from -> increment({arr})",
                    f"Attempted WRITE to invalid register: {arr}",
                    0x10
                    )

        current = self.read(arr=arr)
        current += 1 + t

        self.write(arr=arr, val=current)

    def decrement(self, t=0, arr=0):
        if not 0 <= arr <= self.max_index:
            VMError(IndexError, 
                    f"ERROR | 32-bit register array index out of bounds: r{arr} | Raised from -> increment({arr})",
                    f"Attempted WRITE to invalid register: {arr}",
                    0x10
                    )

        current = self.read(arr=arr)
        current -= 1 + t

        self.write(arr=arr, val=current)    
        

class registers:

    def __init__(self):
        self.regs32 = DwordArray(24) # 24 general-purpose 32-bit registers
        self.ip     = DwordArray(1)  # 32-bit instruction pointer
        self.flags  = {
            "EQ": 0,
            "HI": 0,
            "LO": 0,

        }
        self.sp     = DwordArray(1)  # Stack initialized to 0x00000000



            


class memory:
    MEM_SIZE = 256 * 1024 * 1024

    def __init__(self):
        self.Memory = bytearray(self.MEM_SIZE)

    # ----------------
    # Read operations
    # ----------------

    def read_byte(self, addr):
        return self.Memory[addr]

    def read_word(self, addr):
        return (
            self.Memory[addr]
            | (self.Memory[addr + 1] << 8)
        )

    def read_dword(self, addr):
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
        self.Memory[addr] = val & 0xFF

    def write_word(self, addr, val):
        self.Memory[addr]     = val & 0xFF
        self.Memory[addr + 1] = (val >> 8) & 0xFF

    def write_dword(self, addr, val):
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



