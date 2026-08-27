# Emulator.py

# Import all modules
from Emu.System import System
from Emu.System import SuperIO
# System.py checks for Windows 
 
# Early initialization
 
EmuConsoleColors = System.Teknikality.colors
__last_refresh_frame = None
__can_do_refresh     = False
__refresh_threadExit = False

System.Teknikality.hide_cursor() # Hide the console cursor.

 
def EmuConsoleWarn(msg):
    """Formats the message as a emulator message"""
    System.emu_warn(msg)
 
def EmuConsole(msg, prefix=None):
    """Formats the message as a emulator message"""
    System.sys_write_stdout(f"{prefix if prefix else ''}{EmuConsoleColors.CYAN}Emulator Log:{EmuConsoleColors.BRIGHT_BLACK} {msg}{EmuConsoleColors.RESET}")
 
EmuConsole("Allocating emulator memory...")
Memory = System.memory()
EmuConsole(f"Emulator memory allocated: {len(Memory.Memory)}B")
 
EmuConsole("Allocating virtual registers...")
Registers = System.registers()
EmuConsole(f"Virtual registers allocated: {' '.join([System.format_hex_32(r) for r in Registers.regs32.arr])}")

EmuConsole("Allocating virtual ports...")
PortIO = SuperIO.portio()
EmuConsole("Allocated virtual ports")

EmuConsole("Setting up interrupting devices polling thread...")
Registers.flags["IF"] = 0
InterruptHandler = SuperIO.InterruptHandler(PortIO)
InterruptHandler.InterruptThread()

EmuConsole("Setting up virtual non-interrupting devices...")
NonInterruptDevicesHandler = SuperIO.NonInterruptThreadDevices(memory=Memory, ports=PortIO)

EmuConsole("Main objects initialized")
 
def LoadBinary(path, base_addr=None):
    
    if not System.os.path.isfile(path):
        raise FileNotFoundError(f"Binary not found: {path}")

    if base_addr is None:
        m = System.re.search(r"0x([0-9A-Fa-f]+)", System.os.path.basename(path))
        base_addr = int(m.group(1), 16) if m else 0x00000000

    with open(path, "rb") as f:
        data = f.read()

    end_addr = base_addr + len(data)
    if end_addr > Memory.MEM_SIZE:
        raise ValueError(
            f"'{path}' ({len(data)} bytes) doesn't fit in Memory at "
            f"0x{base_addr:08X}: would end at 0x{end_addr:08X}, "
            f"Memory is 0x{Memory.MEM_SIZE:08X} bytes"
        )

    Memory.Memory[base_addr:end_addr] = data

    EmuConsole(
        f"Loaded '{System.os.path.basename(path)}': {len(data)} bytes @ 0x{base_addr:08X}"
    )

    return base_addr, len(data)


def screen_refresh_thread():
  
  
  def refresh_thread():
    global __can_do_refresh, __last_refresh_frame, __refresh_threadExit
    # Refreshes the screen at 30hz
    # May we have a moment of silence for whatever CPU thread this is running on.
    while not __refresh_threadExit:
      if __can_do_refresh:
          color_map = {
                            130: System.Teknikality.colors.RED,
                            131: System.Teknikality.colors.GREEN,
                            132: System.Teknikality.colors.BLUE,
                            133: System.Teknikality.colors.BRIGHT_BLACK,
                            134: System.Teknikality.colors.CYAN,
                            135: System.Teknikality.colors.BG_RED,
                            136: System.Teknikality.colors.RESET
          }
  
          Fbuf = []
          _pointer = Memory.Map.VIDEO[0]
          while True:
              if _pointer > Memory.Map.VIDEO[1]:
                  break
  
              current_byte = Memory.read_byte(_pointer)
              if current_byte == 0:
                  break
  
              if 10 <= current_byte <= 126:
                  Fbuf.append(chr(current_byte))
              elif current_byte in color_map:
                  Fbuf.append(color_map[current_byte])
  
              _pointer += 1
  
          frame_str = "".join(Fbuf)
  
          # if the frame didn't change, don't do the refresh
          if frame_str == __last_refresh_frame:
              System.time.sleep(0.03333) # ~30hz
              continue
          
          __last_refresh_frame = frame_str
  
          # reset cursor to 0,0 and append the new frame
          System.sys.stdout.write(System.Teknikality.colors.RESET + "\033[H\033[2J" + frame_str + "\033[0J\n\n")
          System.sys.stdout.flush()
  
          System.time.sleep(0.03333) # ~30hz
      else:
          System.time.sleep(0.3) # so it doesn't bully the CPU when we are not refreshing


  t = SuperIO.threading.Thread(target=refresh_thread, daemon=True)
  t.start()
  return t

__Screen_Thread = screen_refresh_thread()

def LoadVMBios():
    """Loads the Emulator BIOS into memory"""
    LoadBinary(path=System.Vars.BIOS_PATH_RELATIVE, base_addr=0x00000000)

def EmuRun():
    """Loads the BIOS then runs the emulator, running cycles."""
    global __can_do_refresh
    LoadVMBios()
    EmuConsole("VM BIOS Loaded into memory @ 0x00000000")
    System.time.sleep(0.5) # Let the user read the logs befor they all get wiped

    System.Teknikality.clearscreen()
    __can_do_refresh = True

    try:
      while True:
        cpu32.step()
        cpu32.interrupt_tick()
    except KeyboardInterrupt:
        __can_do_refresh = False
        System.Teknikality.clearscreen()
        Shutdown()
        
    except Exception as e:
        System.error_window(error_title="VSK-32: Guru Meditation (Fatal Error)", error_message=f"Cannot continue emulator execution. \n\n\nException Type:\n {str(type(e))}", error_code=0x1A)
        Shutdown()


 
def Shutdown():
    """Prints status info, writes a memory dump then gracefully shuts down the Emulator."""
    global __Screen_Thread, __refresh_threadExit

    EmuConsole("Shutting down...")
    EmuConsole("Final State:")
    EmuConsole(f"regs32: {' '.join([str("r") + str(Registers.regs32.arr.index(r)) + str(": 0x") + System.format_hex_32(r) for r in Registers.regs32.arr])}")
    EmuConsole(f"IP:     0x{Registers.ip.read()}")
    EmuConsole(f"SP:     0x{Registers.sp.read()}")
    EmuConsole(f"FLAGS:  {Registers.flags}")
    EmuConsole(f"CYCLE:  {cpu32.current_cycle}")
    
    with open(System.Vars.DUMP_PATH_RELATIVE, "r+b") as f:
      f.seek(0)
      f.write(Memory.Memory)
          
    InterruptHandler._threadExit = True
    InterruptHandler.thread.join()

    __refresh_threadExit = True
    __Screen_Thread.join()
    
    Memory.Memory = bytearray(0)
    del Memory.Memory
    
    System.sys.exit(0)
 
 
 

# MAIN CPU
 
 
 
 
 
 
class cpu32:
    """The main CPU object"""
    class stack:
        """Stack operation helpers"""
        @staticmethod
        def pop():
            """Pops a value from the stack"""
            value = Memory.read_dword(addr=Registers.sp.read())
            Registers.sp.increment(3)
 
            return value
 
        @staticmethod
        def push(val):
            "Pushes a value onto the stack"
            Registers.sp.decrement(3)
            Memory.write_dword(val=val, addr=Registers.sp.read())
 
    class opcodes:
        "Group of opcode variables"
        OPCODE_HALT                                 = 1  # 0x01
        OPCODE_LOAD_IMM32                           = 2  # 0x02
        OPCODE_INDIR_JUMP                           = 3  # 0x03
        OPCODE_ADD                                  = 4  # 0x04
        OPCODE_SUB                                  = 5  # 0x05
        OPCODE_DIV                                  = 6  # 0x06
        OPCODE_MUL                                  = 7  # 0x07
        OPCODE_COMPARE                              = 8  # 0x08
        OPCODE_INDIR_JUMP_EQ                        = 9  # 0x09
        OPCODE_INDIR_JUMP_NE                        = 10 # 0x0A
        OPCODE_INDIR_JUMP_HI                        = 11 # 0x0B
        OPCODE_INDIR_JUMP_LO                        = 12 # 0x0C
        OPCODE_INDIR_COPY_DATA                      = 13 # 0x0D
        OPCODE_WRITE_BYTE                           = 14 # 0x0E
        OPCODE_WRITE_WORD                           = 15 # 0x0F
        OPCODE_READ_BYTE                            = 16 # 0x10
        OPCODE_READ_WORD                            = 17 # 0x11
        OPCODE_MOVE_STACK                           = 18 # 0x12
        OPCODE_PUSH                                 = 19 # 0x13
        OPCODE_POP                                  = 20 # 0x14
        OPCODE_CALL                                 = 21 # 0x15
        OPCODE_RET                                  = 22 # 0x16
        OPCODE_SOFTWARE_INTERRUPT                   = 23 # 0x17
        OPCODE_SOFTWARE_INTERRUPT_RETURN            = 24 # 0x18
        OPCODE_PORT_OUT                             = 25 # 0x19
        OPCODE_PORT_IN                              = 26 # 0x1A
        OPCODE_CLIF                                 = 27 # 0x1B
        OPCODE_SLIF                                 = 28 # 0x1C
        OPCODE_XOR                                  = 29 # 0x1D
        OPCODE_AND                                  = 30 # 0x1E
        OPCODE_NOT                                  = 31 # 0x1F
        OPCODE_COPY_REGISTER                        = 32 # 0x20
        OPCODE_CLEAR_FLAGS                          = 33 # 0x21
       
    current_cycle      = 0
    opcode_total       = 33
    opcode_list        = list(range(1, 34))
    
    EXCEPTION_DISPATCH_TABLE = {
        System.Exceptions.InvalidOpcodeError.UnknownOpcode: 63,
        System.Exceptions.InvalidOpcodeError.InvalidFlags:  62,
        System.Exceptions.InvalidRegister:                  61,
        System.Exceptions.InvalidMemoryWrite:               60,
        System.Exceptions.UnknownError:                     59
    }
 
    @staticmethod
    def fetch8():
        """Fetches a byte at the current IP and increments IP by the number of bytes read"""
        v = Memory.read_byte(addr=Registers.ip.read())
        Registers.ip.increment()
 
        return v
 
    @staticmethod
    def fetch16():
        """Fetches a word at the current IP and increments IP by the number of bytes read"""
        v = Memory.read_word(addr=Registers.ip.read())
        Registers.ip.increment(1)
 
        return v
 
    @staticmethod
    def fetch32():
        """Fetches a dword at the current IP and increments IP by the number of bytes read"""
        v = Memory.read_dword(addr=Registers.ip.read())
        Registers.ip.increment(3)
 
        return v
 
    @staticmethod
    def bits_combine(a, b, blength):    
        return (a << blength) | b
 
    @staticmethod
    def decode_current_ip():
        """Decodes the instruction at the current address in the IP register"""
 
        # Step 1: Read opcode byte
        opcode    = cpu32.fetch8()
        if opcode == 0:
            raise System.Exceptions.InvalidOpcodeError.UnknownOpcode
 
        # Step 2: Read BOP bytes
        a         = cpu32.fetch8()
        b         = cpu32.fetch8()
 
        # step 3: Read 16-bit words, and also supply those two words together (imm16 and extra)
        imm16     = cpu32.fetch16()
        extra     = cpu32.fetch16()
        combined  = cpu32.bits_combine(extra, imm16, 16) # Little endian
 
        # Step 4: Read byte flags
        flags    = cpu32.fetch8()
 
        # Step 5: Return decoded instruction to caller
        return [opcode, a, b, imm16, extra, flags, combined]

    @staticmethod
    def setup_interrupt_environment(ivt_vector):
        """Goes to ivt vector and saves state"""
        cpu32.save_regs()
        cpu32.stack.push(Registers.ip.read())

        Registers.ip.write(val=Memory.read_dword(addr=ivt_vector))



    @staticmethod
    def interrupt_tick():
        """Checks for a interrupt, sets the CPU up for one if it detects one"""

        # If interrupts are disabled, do absolutely nothing.
        if Registers.flags["IF"] == 0:
            return False

        else:
            if InterruptHandler.interrupt_ready:
                InterruptHandler.interrupt_ready = False
                ISR = InterruptHandler.pending * 4 # Multiplicated by 4 to get the real dword address in the IVT

                cpu32.setup_interrupt_environment(ivt_vector=ISR)

                return True

            return False


 
    @staticmethod
    def save_regs():
        """Saves registes to regs32_save"""
        Registers.regs32_save.arr = Registers.regs32.arr.copy()
 
    @staticmethod
    def restore_regs():
        """Restores registers from regs32_save"""
        Registers.regs32.arr = Registers.regs32_save.arr.copy()
 
 
    @staticmethod
    def step():
        """Runs a single fetch>decode>execute tick, does **NOT** check for pending hardware interrupts"""
        try:
          cpu32.run(cpu32.decode_current_ip())           # opcode is a list of ints
        except Exception as e:                           # decode_current_ip() returns that
          fault_isr_id = cpu32.EXCEPTION_DISPATCH_TABLE.get(type(e), cpu32.EXCEPTION_DISPATCH_TABLE[System.Exceptions.UnknownError])
          cpu32.setup_interrupt_environment(fault_isr_id * 4)                
                                                         
        cpu32.current_cycle += 1
 
    @staticmethod
    def run(opcode):
        """Runs an opcode"""
        # Step 1: Extract the opcode
        op     = opcode[0]
        a      = opcode[1]
        b      = opcode[2]
        imm16  = opcode[3] 
        extra  = opcode[4]
        flags  = opcode[5]
        imm32  = opcode[6]  # Note: Combination of imm16 and extra  
 
        # cpu halt
        # FIXEDME: HLT Changed to wait for a interrupt
        if   op == cpu32.opcodes.OPCODE_HALT:
            while True:
                if cpu32.interrupt_tick():
                    break
                System.time.sleep(0.001) 
 
        # load immediate -> register
        elif op == cpu32.opcodes.OPCODE_LOAD_IMM32:
            reg = a
            val = imm32
            
 
            Registers.regs32.write(arr=reg, val=val)
 
        # indirect jump
        elif op == cpu32.opcodes.OPCODE_INDIR_JUMP:
            if   flags == 0:   # immediate jump
                Registers.ip.write(imm32)
            elif flags == 1:   # register jump
                reg = a
                Registers.ip.write(Registers.regs32.read(reg))          
 
            else:
                raise System.Exceptions.InvalidOpcodeError.InvalidFlags
                
 
        # add / sub / div / mul
        elif op == cpu32.opcodes.OPCODE_ADD:
              if   flags == 0:
                  dest = a
                  src  = b
 
                  Registers.regs32.write(arr=dest, val=Registers.regs32.read(dest) + Registers.regs32.read(src))
 
              elif flags == 1:
                  dest = a
                  am   = imm32
 
                  Registers.regs32.write(arr=dest, val=Registers.regs32.read(dest) + imm32)
                 
              else:
                raise System.Exceptions.InvalidOpcodeError.InvalidFlags
        elif op == cpu32.opcodes.OPCODE_SUB:
              if   flags == 0:
                  dest = a
                  src  = b
 
                  Registers.regs32.write(arr=dest, val=Registers.regs32.read(dest) - Registers.regs32.read(src))
 
              elif flags == 1:
                  dest = a
                  am   = imm32
 
                  Registers.regs32.write(arr=dest, val=Registers.regs32.read(dest) - imm32)
                 
              else:
                raise System.Exceptions.InvalidOpcodeError.InvalidFlags           
        elif op == cpu32.opcodes.OPCODE_DIV:
              if   flags == 0:
                  dest = a
                  src  = b
 
                  Registers.regs32.write(arr=dest, val=Registers.regs32.read(dest) // Registers.regs32.read(src))
 
              elif flags == 1:
                  dest = a
                  am   = imm32
 
                  Registers.regs32.write(arr=dest, val=Registers.regs32.read(dest) // imm32)
                 
              else:
                raise System.Exceptions.InvalidOpcodeError.InvalidFlags     
        elif op == cpu32.opcodes.OPCODE_MUL:
              if   flags == 0:
                  dest = a
                  src  = b
 
                  Registers.regs32.write(arr=dest, val=Registers.regs32.read(dest) * Registers.regs32.read(src))
 
              elif flags == 1:
                  dest = a
                  am   = imm32
 
                  Registers.regs32.write(arr=dest, val=Registers.regs32.read(dest) * imm32)
                 
              else:
                raise System.Exceptions.InvalidOpcodeError.InvalidFlags 
 
        # Compares registers or imm32 to a register
        elif op == cpu32.opcodes.OPCODE_COMPARE:
              if   flags == 0:
                  reg_main = a
                  reg_comp = b
                  Registers.flags["EQ"] = Registers.regs32.read(reg_main) == Registers.regs32.read(reg_comp)
                  Registers.flags["LO"] = Registers.regs32.read(reg_main) < Registers.regs32.read(reg_comp)  
                  Registers.flags["HI"] = Registers.regs32.read(reg_main) > Registers.regs32.read(reg_comp)  
        
              elif flags == 1:
                  reg_main = a
                  imm_comp = imm32
                  Registers.flags["EQ"] = Registers.regs32.read(reg_main) == imm_comp
                  Registers.flags["LO"] = Registers.regs32.read(reg_main) < imm_comp
                  Registers.flags["HI"] = Registers.regs32.read(reg_main) > imm_comp
 
              else:
                raise System.Exceptions.InvalidOpcodeError.InvalidFlags
 
 
 
        # jump if equal / lower / higher
        elif op == cpu32.opcodes.OPCODE_INDIR_JUMP_EQ:
            if Registers.flags["EQ"] == 1:
                Registers.ip.write(imm32)
        elif op == cpu32.opcodes.OPCODE_INDIR_JUMP_LO:
            if Registers.flags["LO"] == 1:
                Registers.ip.write(imm32)
        elif op == cpu32.opcodes.OPCODE_INDIR_JUMP_HI:
            if Registers.flags["HI"] == 1:
                Registers.ip.write(imm32)
        elif op == cpu32.opcodes.OPCODE_INDIR_JUMP_NE:
            if Registers.flags["EQ"] == 0:
                Registers.ip.write(imm32)
 
        # 32-bit move
        elif op == cpu32.opcodes.OPCODE_INDIR_COPY_DATA:
 
            # Register -> Immediate Memory
            if   flags == 0:
                reg  = a
                addr = imm32
 
                Memory.write_dword(val=Registers.regs32.read(reg), addr=addr)
 
            # Immediate Memory -> Register
            elif flags == 1:
                reg  = a
                addr = imm32
 
                Registers.regs32.write(arr=reg, val=Memory.read_dword(addr))
 
            # Memory Register -> Register
            elif flags == 2:
                reg_src  = a   # holds the address to read from
                reg_dest = b   # receives the value
 
                read_value = Memory.read_dword(Registers.regs32.read(reg_src))
 
                Registers.regs32.write(arr=reg_dest, val=read_value)
 
            # Register -> Memory Register
            elif flags == 3:
                reg_src  = a   # holds the value to write
                reg_dest = b   # holds the address to write to
 
                addr_dest = Registers.regs32.read(reg_dest)
 
                Memory.write_dword(val=Registers.regs32.read(reg_src), addr=addr_dest)
 
            else:
                raise System.Exceptions.InvalidOpcodeError.InvalidFlags
 
        # 8-bit write
        elif op == cpu32.opcodes.OPCODE_WRITE_BYTE:
            # write_byte does AND masking
            # snips the lower 8 bits
 
            if   flags == 0:
                reg  = a
                addr = imm32
 
                Memory.write_byte(val=Registers.regs32.read(reg), addr=addr)
 
            elif flags == 1:
                reg  = a
                rega = b
                addr = Registers.regs32.read(rega)
 
                Memory.write_byte(val=Registers.regs32.read(reg), addr=addr)
 
            else:
                raise System.Exceptions.InvalidOpcodeError.InvalidFlags
 
        # 16-bit write
        elif op == cpu32.opcodes.OPCODE_WRITE_WORD:
            # write_word does AND masking
            # snips the lower 16 bits
 
            if   flags == 0:
                reg  = a
                addr = imm32
 
                Memory.write_word(val=Registers.regs32.read(reg), addr=addr)
 
            elif flags == 1:
                reg  = a
                rega = b
                addr = Registers.regs32.read(rega)
 
                Memory.write_word(val=Registers.regs32.read(reg), addr=addr)   
 
            else:
                raise System.Exceptions.InvalidOpcodeError.InvalidFlags             
 
        # 8-bit read
        elif op == cpu32.opcodes.OPCODE_READ_BYTE:
            if   flags == 0:
                reg  = a
                addr = imm32
 
                Registers.regs32.write(arr=reg, val=Memory.read_byte(addr=addr))
 
            elif flags == 1:
                reg  = a
                rega = b
                addr = Registers.regs32.read(rega)
 
                Registers.regs32.write(arr=reg, val=Memory.read_byte(addr=addr))
 
            else:
                raise System.Exceptions.InvalidOpcodeError.InvalidFlags
 
        # 16-bit read
        elif op == cpu32.opcodes.OPCODE_READ_WORD:
            if   flags == 0:
                reg  = a
                addr = imm32
 
                Registers.regs32.write(arr=reg, val=Memory.read_word(addr=addr))
 
            elif flags == 1:
                reg  = a
                rega = b
                addr = Registers.regs32.read(rega)
 
                Registers.regs32.write(arr=reg, val=Memory.read_word(addr=addr))
 
            else:
                raise System.Exceptions.InvalidOpcodeError.InvalidFlags
 
        # Moves SP
        elif op == cpu32.opcodes.OPCODE_MOVE_STACK:
            if   flags == 0:
                addr = imm32
 
                Registers.sp.write(addr)
 
            elif flags == 1:
                reg  = a
                addr = Registers.regs32.read(reg)
 
                Registers.sp.write(addr)
 
            else:
                raise System.Exceptions.InvalidOpcodeError.InvalidFlags  
                 
        # push/pop stack ops        
        elif op == cpu32.opcodes.OPCODE_PUSH:
            if   flags == 0:
                val  = imm32
 
                cpu32.stack.push(val)    
 
            elif flags == 1:
                val  = Registers.regs32.read(a)
 
                cpu32.stack.push(val)   
                
            else:
                raise System.Exceptions.InvalidOpcodeError.InvalidFlags
        elif op == cpu32.opcodes.OPCODE_POP:
            reg = a
           
            Registers.regs32.write(arr=reg, val=cpu32.stack.pop())
 
        # call/ret
        elif op == cpu32.opcodes.OPCODE_CALL:
            addr = imm32
 
            cpu32.stack.push(Registers.ip.read())
            Registers.ip.write(addr)
        elif op == cpu32.opcodes.OPCODE_RET:
            addr = cpu32.stack.pop()
            Registers.ip.write(addr)
 
        # int
        elif op == cpu32.opcodes.OPCODE_SOFTWARE_INTERRUPT:
            code = a * 4
            # multiplicated by 4 so it points to the next dword entry
 
            # ISR Entries are dwords
            cpu32.setup_interrupt_environment(ivt_vector=code)
 
        # interrupt return
        elif op == cpu32.opcodes.OPCODE_SOFTWARE_INTERRUPT_RETURN:
            Registers.ip.write(cpu32.stack.pop())
            cpu32.restore_regs()

        elif op == cpu32.opcodes.OPCODE_PORT_OUT:
            reg_val = Registers.regs32.read(a)  # Holds the value to write

            if   flags == 0:
                reg_port = Registers.regs32.read(b)  # Holds the port to write

                PortIO.write(port=reg_port, value=reg_val)
                
                # Also refresh devices
                NonInterruptDevicesHandler.PollAllDevices()

            elif flags == 1:
                port = imm16

                PortIO.write(port=port, value=reg_val)

                # Also refresh devices
                NonInterruptDevicesHandler.PollAllDevices()

            else:
                raise System.Exceptions.InvalidOpcodeError.InvalidFlags

        elif op == cpu32.opcodes.OPCODE_PORT_IN:
            reg_dest = a # Holds the register name to put the read value in

            if   flags == 0:
                port = Registers.regs32.read(b)

                Registers.regs32.write(arr=reg_dest, val=PortIO.read(port))

            elif flags == 1:
                port = imm16

                Registers.regs32.write(arr=reg_dest, val=PortIO.read(port))

            else:
                raise System.Exceptions.InvalidOpcodeError.InvalidFlags

        elif op == cpu32.opcodes.OPCODE_CLIF:
            Registers.flags["IF"] = 0
        
        elif op == cpu32.opcodes.OPCODE_SLIF:
            Registers.flags["IF"] = 1

        elif op == cpu32.opcodes.OPCODE_XOR:
            Registers.regs32.write(
                arr=a,
                val=Registers.regs32.read(a) ^ Registers.regs32.read(b)
            )
        
        elif op == cpu32.opcodes.OPCODE_AND:
            Registers.regs32.write(
                arr=a,
                val=Registers.regs32.read(a) & Registers.regs32.read(b)
            )
        
        elif op == cpu32.opcodes.OPCODE_NOT:
            Registers.regs32.write(
                arr=a,
                val=(~Registers.regs32.read(a)) & 0xFFFFFFFF
            )

        elif op == cpu32.opcodes.OPCODE_COPY_REGISTER:
            rega = a
            regb = b

            Registers.regs32.write(arr=a, val=Registers.regs32.read(regb))

        elif op == cpu32.opcodes.OPCODE_CLEAR_FLAGS:
            Registers.flags["EQ"] = 0
            Registers.flags["HI"] = 0
            Registers.flags["LO"] = 0
            # Dont touch IF - comparison flags only.

            
 
EmuRun()
 
 
 
                    
 
               
                
 
 
 
 
 
 
 



