33 Opcodes, BIOS, 24 32-bit registers, byte-addressed, 256-dword PMIO, 256MiB RAM, 512MiB 1024B/sector disk

<img width="273" height="75" alt="image" src="https://github.com/user-attachments/assets/0f046ddd-f35a-40aa-89c1-87bc87cf66c9" />
<img width="832" height="198" alt="image" src="https://github.com/user-attachments/assets/72eb771b-7ce9-487b-bf80-316330c42697" />


Requires python >3.12 (Built on 3.14.3)

Emulator.py: Main emulator runtime
ssfs.py:     SSFS disk image reader (custom filesystem)
vsk32env.py: Environment handler
HTML doc:    Vibe coded HTML documentation 

Assembler and GUI parts of System.py were vibe coded

Includes BIOS source

To setup the enviroment:

Put the VSK-32 Parent folder wherever you want 

Navigate to VSK-32/ in cmd or powershell >>> `cd "path-to-VSK-32"`

Run these commands:

```
PS C:\python\VSK-32> py vsk32env.py WriteVMDisk
Created 'Storage/Disk/vmdisk.img'
PS C:\python\VSK-32> py vsk32env.py WriteMEMDump
Created 'Memory Dump/dump.bin'
```

Now, run the emulator:

`py Emulator.py --legacyvideo true`
you can also launch with legacy video as false to use the dearGUI video GUI - it works but is still in beta

Also contains a `add_to_path.py` file that adds `com/` to path and adds the following commands:
  -> vsk32:      Emulator.py (new commands added - see below)
  -> vsk32env:   vsk32env.py
  -> asm-x32:    Assembler/x32sm.py
  -> ssfsimage:  Assembler/image.py

vsk32 commands:
  -> --image <path>:           boot from this image
  -> --legacyvideo <state>:    use legacy (console out) video instead of the DearGUI one
  -> --norun <state>:          toggle on/off running the emulator once command parsing is done
  -> --videofont <path>:       path to .ttf path for the DearGUI video
  -> --setdefaultfont <path>:  set this font file as the default font
  -> --dbg <state>:            toggle on/off the GUI debugger (displays registers and a  live memory/stack dump)

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

Then press `ctrl+c` in the console to shut down the emulator

For OSes, see VS-OS and Quasix.
