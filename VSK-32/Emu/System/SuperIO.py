# SuperIO.py

# Lib imports
import threading
import sys
import msvcrt
import time

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
        self.pending            = 0         # Holds a pending ISR
        self.interrupt_ready    = False     # Tells the CPU that a ISR is pending
        self.ports              = ports     # Reference to a initialized port buffer

        self.thread             = None
        self._threadExit        = False     # Used to signal thread shutdown
    
      
    def InterruptThread(self):
        devices = [InterruptCausingDevices.Keyboard]

        def Internal():
           while not self._threadExit:      
              for device in devices:
                  isr = device.poll() # [isr, port, val]

                  if isr:
                      self.ports.write(port=isr[1], value=isr[2])
                      self.pending = isr[0]
    
                      self.interrupt_ready = True

              time.sleep(0.001) # 1ms

           sys.exit() # Immediately exit upon exit flag 

        self.thread = threading.Thread(target=Internal, daemon=True)
        self.thread.start()







class PORTs:
    KB_PORT = 1

class ISRs:
    KB_ISR = 0x01


class InterruptCausingDevices:
    class Keyboard:
        @staticmethod
        def poll():
            key = sys_getkey()

            if not key:
                return False

            else:
                data = InterruptCausingDevices.Keyboard.doKeyboardInterrupt(key=key)

                return data

        def doKeyboardInterrupt(key):
            port = PORTs.KB_PORT
            val  = key

            return [ISRs.KB_ISR, port, val]
            






def sys_getkey():
    if msvcrt.kbhit():
        char = msvcrt.getch()
        return ord(char)

    return False