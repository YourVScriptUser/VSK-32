"""SSFS Image File reader"""

import sys
import os
SSFS_SECTOR_SIZE = 1024 # SSFS uses 1024B sectors
SSFS_FILE_MAGIC  = 0xFE # Signals a new file entry
SSFS_NAME_MAGIC  = 0xFD # Signals the string file name 

# Directory (sector 4) entry format, 30 bytes each, up to 34 entries:
#    offset  size  field
#    0       1     0xFE  (File Entry magic)
#    1       4     start sector
#    5       4     length in sectors
#    9       1     0xFD  (File Descriptor magic)
#    10      20    filename, ASCII, NUL-padded

def read_dword_from_byteslist(cursor, b):
    return (
        b[cursor]
        | (b[cursor + 1] << 8)
        | (b[cursor + 2] << 16)
        | (b[cursor + 3] << 24)
    )

def read_sectors(filepath, sector_start, sector_end):
    byte_start = sector_start * SSFS_SECTOR_SIZE
    byte_end   = sector_end   * SSFS_SECTOR_SIZE
    if byte_start == byte_end:
        byte_end += SSFS_SECTOR_SIZE
    
    if not os.path.exists(filepath):
        print(f"{filepath}: File not found.")
        return 2
    
    print(f"Reading sectors {sector_start}-{sector_end} of image '{filepath}'")
    with open(filepath, "rb") as f:
        file_image = f.read()
        
    sectorslice = file_image[byte_start:byte_end]
    return sectorslice

def read_by_sector(filepath):
    if not os.path.exists(filepath):
        print(f"'{filepath}': File not found.")
        return 2
    
    print(f"Reading '{filepath}'")
    size = os.path.getsize(filepath)
    print(f"Disk image is {size} bytes large / {size // SSFS_SECTOR_SIZE} sectors\n")
    print("Reading image...")
    with open(filepath, "rb") as f:
        file_image = f.read()
        
    print("Reading metadata sector...")    
    metadata_sector = 4 * SSFS_SECTOR_SIZE
    metadata_sector_end = metadata_sector + SSFS_SECTOR_SIZE
    
    sector_extract = file_image[metadata_sector:metadata_sector_end]
    print("Extracted metadata sector")
    
    print("Reading files present...")
    
    curs =       0
    data =       0
    filesfound = 0
    files =     {}
    while True:
        print(f"\rFound {filesfound} files... Byte {curs} of metadata sector", end="")
        # If the data is 0, we have hit the end of the metadata sector
        if curs >= SSFS_SECTOR_SIZE:
            print("\nREAD SUCCESS: Hit end of metadata sector")
            return files
        
        
        data = sector_extract[curs]
        
        
        
        if data == SSFS_FILE_MAGIC:
            curs += 1
            sector_start = read_dword_from_byteslist(cursor=curs, b=sector_extract)
            
            curs += 4 # +4 because its a dword
            sector_len   = read_dword_from_byteslist(cursor=curs, b=sector_extract)
            sector_end = sector_start + (sector_len - 1)
            curs += 4
            
            sectors_taken = sector_len
            v_filesize    = sectors_taken * SSFS_SECTOR_SIZE
    
            data = sector_extract[curs]
            if data != SSFS_NAME_MAGIC:
                print(f"\nREAD FAILED: Metadata sector corrupt.")
                return 1
                
            else:
                curs += 1
                data = sector_extract[curs]   
                
                # Now extract the string name
                # Strings are fixed-length of 20 bytes
                string_b = sector_extract[curs:curs+20]
                fullstring = ""
                for al in string_b:
                    fullstring = fullstring + chr(al)
                    
                fullstring = fullstring.strip("\x00")
                curs += 20 # Skip string
                
                # We found a file
                files[fullstring] = {"_size": v_filesize, "_sector_start": sector_start, "_sector_end": sector_end}
                filesfound += 1
        else:
          curs += 1
    
if __name__ == "__main__":
    args = sys.argv
    if len(args) <= 2:
        print("Expected command and path")
        print("Commands:")
        print(" ls   <imagepath>: List files on <imagepath>")
        print(" read <imagepath> <filename> <readtype>: Read the bytes of the file <filename> in the disk image <imagepath>, <readtype> decides if you want to print the output in ascii (unicode) or hex")
        sys.exit(1)
        
    else:
        command = args[1]
        path = args[2]
        
        if command == "ls":
           files = read_by_sector(path)
           if not isinstance(files, dict):
               print(f"Failed to read: '{path}'")
               sys.exit(1)
           
           print("\n\n")
           for file, info in files.items():
               print(f"{file:<15}   |  Size: {info["_size"]} Sectors: {info["_sector_start"]}-{info["_sector_end"]}")
              
        if command == "read":
           if len(args) <= 4:
               print("Expected filename and read type")
               sys.exit(1)
               
           filename = args[3]    
           readtype = args[4]
           files    = read_by_sector(path)
   
           if not isinstance(files, dict):
               print(f"Failed to read: '{path}'")
               sys.exit(1)
           
           if filename not in files:
               print(f"{filename}: File not found inside image")
               sys.exit(1)
               
           sector_start = files[filename]["_sector_start"]
           sector_end   = files[filename]["_sector_end"]    
               
           sectorbytes = read_sectors(path, sector_start, sector_end)
           
           if readtype not in ["ascii", "hex"]:
               print("Invalid readtype, defaulting to ascii")
               readtype = "ascii"
           
           if readtype == "ascii":
               print()
               for b in sectorbytes:
                   print(chr(b), end="")
                
           elif readtype == "hex":
               l = 30
               print()
               for i, b in enumerate(sectorbytes):
                   print(str(f'{b:02X}') + " ", end="")
                   if (i+1) % l == 0:
                       print()
               
               
           
            
            
        