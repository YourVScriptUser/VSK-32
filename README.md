33 Opcodes, BIOS, 34 32-bit registers, byte-addressed, 256-dword PMIO, 256MiB RAM, 512MiB 1024B/sector disk

Requires python >3.12 (Built on 3.14.3)

Emulator.py: Main emulator runtime
ssfs.py:     SSFS disk image reader (custom filesystem)
vsk32env.py: Environment handler
HTML doc:    Vibe coded HTML documentation 

Assembler and GUI parts of System.py were vibe coded

Includes BIOS source

To setup the enviroment:

Put the VSK-32 Parent folder wherever you want choose

Navigate to VSK-32/ in cmd or powershell >>> `cd "path-to-VSK-32"`

Run these commands:

```
PS C:\python\VSK-32> py vsk32env.py WriteVMDisk
Created 'Storage/Disk/vmdisk.img'
PS C:\python\VSK-32> py vsk32env.py WriteMEMDump
Created 'Memory Dump/dump.bin'
```

Now, run the emulator:

`py Emulator.py`

Expected output:

Should display some logs first, then the BIOS should start:

```
VSK Software sysROM BIOS v1.0.0
VSK-32 Proprietary ROM BIOS

Initializing hardware... done
Initializing interrupts... done
Reading boot sector... fail

Boot Failed: Not a bootable disk.
```

Then press `ctrl+c` to shut down the emulator

For OSes, see VS-OS and Quasix.
