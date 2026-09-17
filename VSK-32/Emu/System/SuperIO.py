# SuperIO.py

# Local imports
from Emu.System              import Vars
from Emu.Exceptions          import Exceptions

# Lib imports
import threading
import sys
import msvcrt
import time
import os

class portio:
    """Main PMIO class"""
    def __init__(self):
        self.ports = [0] * 256 # 256 Ports (each value is a dword)
        self.mask  = 0xFFFFFFFF

    def write(self, value, port):
        value &= self.mask
        self.ports[port] = value
 
    def read(self, port):
        return self.ports[port]

class InterruptHandler:
    def __init__(self, ports):
        self.pending            = 0         # Holds pending ISRs
        self.interrupt_ready    = False     # Tells the CPU that a ISR is pending
        self.ports              = ports     # Reference to a initialized port buffer

        self.thread             = None
        self._threadExit        = False     # Used to signal thread shutdown
    
      
    def InterruptThread(self):
        devices = [InterruptCausingDevices.Keyboard, InterruptCausingDevices.PIT]

        def Internal():
           while not self._threadExit:      
              for device in devices:
                  isr = device.poll(self.ports) # [isr, port, val, do_port]

                  if isr:
                      if isr[3]:
                        self.ports.write(port=isr[1], value=isr[2])
                      self.pending = isr[0]
    
                      self.interrupt_ready = True

              time.sleep(0.001) # 1ms

        self.thread = threading.Thread(target=Internal, daemon=True)
        self.thread.start()







class PORTs:
    KB_PORT                    = 0x4B # The keyboard port, holds the key pressed
    
    STORAGE_STATUS_NOTIFY_PORT = 0x00 # Tells the disk to do something 
    STORAGE_SECTOR_PORT        = 0xEA # Disk sector port
    STORAGE_ADDRESS_PORT       = 0xEB # Where the disk writes the sector to memory
    STORAGE_STORAGE_MODE       = 0xEC # Disk mode port 1 = read, 2 = write
    
    PIT_INTERVAL_PORT          = 0x02 # Holds the current interrupt interval (in seconds)
    PIT_ENABLE_PORT            = 0x01 # 1=do interrupt, 0=dont interrupt
    
    VIDEO_START_ADDR_PORT      = 0xDC # Start address of video MMIO
    VIDEO_END_ADDR_PORT        = 0xDD # End   address of video MMIO
    VIDEO_RENDER_CURSOR_BOOL   = 0xDE # 0=no cursor, 1=yes cursor (char is '▂')

class ISRs:
    KB_ISR    = 0x01                     # Keyboard interrupt routine (id - not address!)
    PIT_ISR   = 0x02                     # PIT Timer interrupt


class InterruptCausingDevices:
    class Keyboard:
        @staticmethod
        def poll(p):
            key = sys_getkey()

            if not key:
                return False

            else:
                data = InterruptCausingDevices.Keyboard.doKeyboardInterrupt(key=key)

                return data

        def doKeyboardInterrupt(key):
            port = PORTs.KB_PORT
            val  = key

            return [ISRs.KB_ISR, port, val, True]
            
    class PIT:
      last_tick = time.monotonic()
  
      @staticmethod
      def poll(p):
          if p.read(PORTs.PIT_ENABLE_PORT) != 1:
              return False
  
          interval = p.read(PORTs.PIT_INTERVAL_PORT)
  
          now = time.monotonic()
  
          if now - InterruptCausingDevices.PIT.last_tick < interval:
              return False
  
          InterruptCausingDevices.PIT.last_tick += interval
  
          return InterruptCausingDevices.PIT.doPITInterrupt()
  
      @staticmethod
      def doPITInterrupt():
          return [ISRs.PIT_ISR, 0, 0, False]




def sys_getkey():
    if msvcrt.kbhit():
        char = msvcrt.getch()
        return ord(char)

    return False


class NonInterruptThreadDevices:
    def __init__(self, ports, memory):
        self.ports  = ports
        self.memory = memory
  
    def PollAllDevices(self):
        for device in DEVICES:
            device.poll(ports=self.ports, memory=self.memory)

    class Disk:
        @staticmethod
        def poll(ports, memory):
            # Read status port
            is_ready = ports.read(port=PORTs.STORAGE_STATUS_NOTIFY_PORT)
            mode     = ports.read(port=PORTs.STORAGE_STORAGE_MODE) 
             # 1 = read
             # 2 = write
             
            if not os.path.exists(Vars.DISK_PATH_RELATIVE):
                Exceptions.warning_window(f"Emulator virtual disk missing!\nPath: '{Vars.DISK_PATH_RELATIVE}'", "Disk Missing")
                return # Cannot run shutdown here, just return.
                       # The user will enjoy multiple error windows shoved in their face
 
            if not is_ready or mode not in [1, 2]:
                return

            else:
              if   mode == 1: 
                sector  = ports.read(port=PORTs.STORAGE_SECTOR_PORT )
                address = ports.read(port=PORTs.STORAGE_ADDRESS_PORT)
                if sector >= Vars.DISK_END_SECTOR:
                    return 

                with open(Vars.DISK_PATH_RELATIVE, "rb") as f:
                    byte = sector * Vars.DISK_SECTOR_SIZE 
                    f.seek(byte)

                    read = f.read(Vars.DISK_SECTOR_SIZE) 

                for b in read:
                    memory.write_byte(val=b, addr=address)
                    address += 1

              elif mode  == 2:
                 sector  = ports.read(port=PORTs.STORAGE_SECTOR_PORT )
                 address = ports.read(port=PORTs.STORAGE_ADDRESS_PORT)
                 if sector >= Vars.DISK_END_SECTOR:
                     return                   
                 
                 with open(Vars.DISK_PATH_RELATIVE, "r+b") as f:
                     byte = sector * Vars.DISK_SECTOR_SIZE
                     read = bytearray(0)
                     
                     offset = address
                     for _ in range(Vars.DISK_SECTOR_SIZE):
                         read.append(memory.read_byte(offset))
                         offset += 1
                         
                     f.seek(byte)
                     f.write(read)
                         
DEVICES = [NonInterruptThreadDevices.Disk]
