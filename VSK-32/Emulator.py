# Emulator.py

# Import all modules
from Emu.System import System

# Early initialization

EmuConsoleColors = System.Teknikality.colors

if System.os.name != "nt":
    raise OSError("Windows-only program.")

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

EmuConsole("Main objects initialized")










# MAIN CPU






class cpu32:
    """The main CPU object"""
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
        

    is_halted = True

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
            print(f"Decoded NULL opcode. Address={Registers.ip.read()}")
            exit()

        # Step 2: Read BOP bytes
        a         = cpu32.fetch8()
        b         = cpu32.fetch8()

        # step 3: Read 16-bit words, and also supply those two words together (imm16 and extra)
        imm16     = cpu32.fetch16()
        extra     = cpu32.fetch16()
        combined  = cpu32.bits_combine(imm16, extra, 16)

        # Step 4: Read byte flags
        flags    = cpu32.fetch8()

        # Step 5: return to caller
        return [opcode, a, b, imm16, extra, flags, combined]
    

    


    @staticmethod
    def step():
        """Runs a single fetch>decode>execute tick"""
        cpu32.run(cpu32.decode_current_ip())             # opcode is a list of ints
                                                         # decode_current_ip() returns that

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
        # (FIXME) FUTURE: Make this sleep until a interrupt is raised instead
        if   op == cpu32.opcodes.OPCODE_HALT:
            cpu32.is_halted = True 

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
                ...
                # (FIXME) FUTURE: Add an exception raise here

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
                  ...
                  # (FIXME) FUTURE: Add an exception raise here
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
                  ...
                  # (FIXME) FUTURE: Add an exception raise here              
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
                  ...
                  # (FIXME) FUTURE: Add an exception raise here        
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
                  ...
                  # (FIXME) FUTURE: Add an exception raise here   

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
                  ...
                  # (FIXME) FUTURE: Add an exception raise here 



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
                ...
                # (FIXME) FUTURE: Add an exception raise here

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
                ...
                # (FIXME) FUTURE: Add an exception raise here

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
                ...
                # (FIXME) FUTURE: Add an exception raise here                

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
                ...
                # (FIXME) FUTURE: Add an exception raise here

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
                ...
                # (FIXME) FUTURE: Add an exception raise here

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
                ...
                # (FIXME) FUTURE: Add an exception raise here     
                 
        # push/pop stack ops         
        elif op == cpu32.opcodes.OPCODE_PUSH:
            if   flags == 0:
                val  = imm32

                Registers.sp.decrement(3) 
                Memory.write_dword(val=val, addr=Registers.sp.read())     

            elif flags == 1:
                val  = Registers.regs32.read(a)

                Registers.sp.decrement(3) 
                Memory.write_dword(val=val, addr=Registers.sp.read())
                
            else:
                ...
                # (FIXME) FUTURE: Add an exception raise here 

        elif op == cpu32.opcodes.OPCODE_POP:
            reg = a

            value = Memory.read_dword(addr=Registers.sp.read())
            Registers.regs32.write(arr=reg, val=value)
            Registers.sp.increment(3)

                     

                
                







cpu32.is_halted = False

start = System.time.perf_counter()
ins = 0
while not cpu32.is_halted:
    cpu32.step()
    ins += 1

end = System.time.perf_counter()
    
print(f"Halt state: {cpu32.is_halted} (Took: {round(((end - start)), 2) } seconds, {ins} instructions ran)")
print(f"{' '.join([System.format_hex_32(r) for r in Registers.regs32.arr])}")
