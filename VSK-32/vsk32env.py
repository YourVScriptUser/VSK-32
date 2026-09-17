# vsk32env.py
from Emu.System import Vars

"""
A simple command-line that edits VM state
"""


import sys
import os

if len(sys.argv) == 1:
    print("Expected command")
    sys.exit(1)

command  = sys.argv[1]


if command == "WriteVMDisk":
    with open(Vars.DISK_PATH_RELATIVE, "wb") as f:
      f.write(b"\x00" * (512 * 1024 * 1024))
      
    print("Created 'VM_DISK/vmdisk.img'")
    sys.exit(0)
    
elif command == "WriteMEMDump":   
    with open(Vars.DUMP_PATH_RELATIVE, "wb") as f:
      f.write(b"\x00" * (256 * 1024 * 1024))
          
    print("Created 'M_DUMP/dump.bin'")
    sys.exit(0) 
    
elif command == "WriteBIOS":   
    with open(Vars.BIOS_PATH_RELATIVE, "wb") as f:
      f.write(b"\x00" * (21 * 1024))
          
    print("Created 'VM_BIOS/bios.rom'")
    sys.exit(0)


elif command == "LoadDiskImage":
    if len(sys.argv) < 3:
        print("Usage: LoadDiskImage <path-to-bin> [offset]")
        sys.exit(1)

    src_path = sys.argv[2]
    offset   = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0  # base 0 lets you pass hex like 0x1000

    disk_path = Vars.DISK_PATH_RELATIVE

    if not os.path.isfile(src_path):
        print(f"Source file not found: {src_path}")
        sys.exit(1)

    if not os.path.isfile(disk_path):
        print(f"Disk image not found: {disk_path} (run WriteVMDisk first)")
        sys.exit(1)

    disk_size = os.path.getsize(disk_path)
    data_size = os.path.getsize(src_path)

    if offset < 0:
        print(f"Offset must be non-negative, got {offset}")
        sys.exit(1)

    if offset + data_size > disk_size:
        print(
            f"'{src_path}' ({data_size} bytes) doesn't fit in disk at "
            f"offset {offset}: would end at byte {offset + data_size}, "
            f"disk is {disk_size} bytes"
        )
        sys.exit(1)

    with open(src_path, "rb") as f:
        data = f.read()

    with open(disk_path, "r+b") as f:
        f.seek(offset)
        f.write(data)

    print(f"Loaded '{src_path}': {data_size} bytes @ offset {offset} into '{disk_path}'")
    sys.exit(0)
    
# Hacked copy of LoadDiskImage    
elif command == "UpdateBIOS":
    if len(sys.argv) < 3:
        print("Usage: UpdateBIOS <path-to-bin>")
        sys.exit(1)

    src_path = sys.argv[2]
    offset   = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0  # base 0 lets you pass hex like 0x1000

    disk_path = Vars.BIOS_PATH_RELATIVE

    if not os.path.isfile(src_path):
        print(f"Source file not found: {src_path}")
        sys.exit(1)

    if not os.path.isfile(disk_path):
        print(f"BIOS binary not found: {disk_path} (run WriteBIOS first)")
        sys.exit(1)

    disk_size = os.path.getsize(disk_path)
    data_size = os.path.getsize(src_path)

    if offset + data_size > disk_size:
        print(
            f"'{src_path}' ({data_size} bytes) doesn't fit in disk at "
            f"offset {offset}: would end at byte {offset + data_size}, "
            f"disk is {disk_size} bytes"
        )
        sys.exit(1)

    with open(src_path, "rb") as f:
        data = f.read()

    with open(disk_path, "r+b") as f:
        f.seek(offset)
        f.write(data)

    print(f"Loaded '{src_path}': {data_size} bytes @ offset {offset} into '{disk_path}'")
    sys.exit(0)  
    
else:
    print("Invalid command. Valid commands are: WriteBIOS, WriteVMDisk, LoadDiskImage, UpdateBIOS, WriteMEMDump")