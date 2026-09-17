# Exceptions.py
import ctypes
import threading
import sys

class InvalidOpcodeError:
    class InvalidFlags(Exception): ...
    
    class UnknownOpcode(Exception): ...
    
    class SomethingElse(Exception): ...
    
class InvalidMemoryWrite(Exception): ...

class InvalidRegister(Exception): ...

class UnknownError(Exception): ...

def warning_window(error_message, error_title):
      """blocking warning window"""
      u_type = 0x0 | 0x30
      
      ctypes.windll.user32.MessageBoxW(0, f"{error_message}", error_title, u_type)
      sys.exit(0)
       
  

