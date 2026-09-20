#!/usr/bin/env python3
"""
image.py - Builds a full VSK-32 disk image from a flat directory of OS
source/asset files, configured by a .fiex build-config file instead of
CLI flags.

    python3 image.py OS_DIR -o os.img
    python3 vsk32env.py LoadDiskImage os.img
    (done)

Build configuration (com/.fiex):
    Every build needs OS_DIR/com/.fiex -- a small text file, one directive
    per line, that replaces what used to be CLI flags. All four directive
    kinds below are MANDATORY; a build fails with a clear error if any is
    missing. `com/` is metadata-only: nothing else placed there gets
    assembled or packed onto the disk, and it isn't scanned as an OS file
    directory itself.

    Syntax:
        // this is a comment, runs to end of line
        docompile {.x32, .asm}          // which extensions get assembled
        sinboot   {boot.x32}              // single-sector boot loader file
        extboot   {ext_boot.x32}            // extended boot loader file
        symfile   {SYMBOLS.SYM}               // on-disk name of the symbol table
        ext       {KERNEL.x32, .BANANA}         // per-file output extension override

    docompile {ext, ext, ...}
        Extensions (with the leading dot, comma-separated) that get
        assembled by x32sm.py. A file in OS_DIR whose extension is NOT in
        this list is still packed onto the disk, just copied byte-for-byte
        instead of assembled (e.g. font.raw, splash.data).

    sinboot {file} / extboot {file}
        Exact filename (as it appears in OS_DIR, with extension) of the
        single-sector boot loader and the extended (3-sector) boot loader.
        Same two files as the old --sinbootloader/--extbootloader flags.

    symfile {name}
        On-disk filename for the emitted symbol table (see "Symbol file"
        below). There's no way to omit it now that this is mandatory --
        every build produces a symbol file.

    ext {file, .NEWEXT}
        Overrides the OUTPUT extension for exactly that one assembled
        file -- e.g. `ext {KERNEL.x32, .BANANA}` makes that file come out
        as KERNEL.BANANA instead of the default KERNEL.BIN. Every other
        assembled file is unaffected and still defaults to .BIN. Can
        appear multiple times, once per file needing an override. `file`
        must match a real file in OS_DIR that's also covered by
        `docompile` (i.e. actually gets assembled) -- referencing a file
        that doesn't exist, or one whose extension isn't in `docompile`,
        is a hard build error.

        The literal keyword NoExt (instead of a .EXTENSION) strips the
        extension entirely, no trailing dot: `ext {file.x32, NoExt}`
        produces a disk file named exactly `file`, with nothing after it.

    Referencing a nonexistent file anywhere in sinboot/extboot/ext is a
    hard build error, not a silent skip.

Layout written to the disk image:
    Sector 0        sinboot file, assembled                    (1024 B)
    Sectors 1-3     extboot file, assembled                     (3072 B)
    Sector 4        file directory (magic-byte format, see below)
    Sector 5+       every other file in OS_DIR, in os.listdir() order

Directory (sector 4) entries also ALIAS the boot loader and extended boot
loader, so they're loadable like any other file (e.g. via B_LOAD_FILE)
without duplicating their bytes anywhere:
    <sinboot stem>.BOOT   -> sector 0            (1 sector)
    <extboot stem>.BOOT   -> sectors 1-3           (3 sectors)
(stem = source filename with its extension stripped -- e.g. boot.x32 ->
boot.BOOT, NOT boot.x32.BOOT. This naming is fixed and NOT affected by
`ext {}` overrides, which only apply to regular OS_DIR files.)
These entries point at the SAME fixed sectors the BIOS/boot chain already
hardwires -- the sinboot file still has to physically live at sector 0
and the extboot file at sectors 1-3 for the boot process itself to work;
this only adds a way to look them up and load copies of them by name at
runtime, e.g. for a "reinstall bootloader" tool or a rescue kernel.

Directory (sector 4) entry format, 30 bytes each, up to 34 entries:
    offset  size  field
    0       1     0xFE  (File Entry magic)
    1       4     start sector, u32 LE
    5       4     length in sectors, u32 LE
    9       1     0xFD  (File Descriptor magic)
    10      20    filename, ASCII, NUL-padded

A directory entry whose first byte is 0x00 (not 0xFE) marks the end of the
list -- the OS-side parser stops there rather than needing an explicit
count.

On-disk filenames:
    kernel.asm  -> KERNEL.BIN   (assembled sources default to .BIN unless
    driver.x32  -> DRIVER.BIN    overridden by an `ext {}` directive)
    font.raw    -> FONT.RAW     (anything not in `docompile`'s extension
    splash.data -> SPLASH.DATA   list is copied as-is, disk name unchanged)
    Names (including extension) longer than 20 bytes are a hard error.

    IMPORTANT -- case is preserved exactly, and lookup is case-SENSITIVE:
    the disk name keeps whatever case the source filename's stem used
    (Kernel.asm -> Kernel.BIN, kernel.asm -> kernel.BIN, KERNEL.asm ->
    KERNEL.BIN). If a file needs to look itself up by name (e.g. a kernel
    reading its own filename to self-verify, or ANY code embedding a
    filename string to pass to load_file), that string must match the
    source file's actual on-disk stem byte-for-byte, including case --
    the OS-side directory lookup does a plain byte compare, no case-
    folding. Getting this wrong doesn't error at build time; the file
    just silently fails to be found at boot.

Cross-file linking:
    sinboot, extboot, and every OS_DIR source file (per `docompile`) can
    all call labels defined in one another (e.g. shell.asm calling a
    routine exported by kernel.asm). This works in two passes:
      Pass 1: assemble every source file standalone, just to harvest its
              resolved label table (addresses only -- these files must set
              their own absolute load address with `origin`, since there's
              no relocation in this ISA and the tool can't invent
              addresses for you).
      Pass 2: assemble every source file again, this time importing every
              OTHER file's Pass 1 EXPORTED labels as externs, and using
              the real output. Defining a LOCAL label with the same name
              as an imported (extern) one is a hard build error -- not
              silent shadowing -- since it's a way to accidentally lose
              access to the intended cross-file label with no warning.
              Rename one of the two colliding labels to fix it (see
              x32sm.py's extern_labels docs for the exact error).
    Raw (non-source) files aren't part of this -- they have no labels.

    Which labels a file exports is controlled by `global <name>` lines
    in that source file (see x32sm.py's module docstring for the exact
    syntax/rules): a file with at least one `global` line only exports
    the names it explicitly lists there, so two files can freely reuse
    the same private (non-exported) label name without colliding -- the
    collision error above only fires against names that are actually
    visible as externs, never against another file's private labels. A
    file with NO `global` lines exports every label it defines,
    unchanged from how this worked before `global` existed -- so
    existing sources keep linking exactly as before until you opt a
    file into the restricted behavior by adding its first `global` line
    (at which point its previously-shared names become collision-
    checked like any other export).

Symbol file (symfile {name} in .fiex):
    Every resolved label from EVERY assembled unit (sinboot, extboot, and
    every OS_DIR source file) is written to disk as a file with the given
    name, packed last, after every other file. It's an ordinary SSFS
    file -- gets its own directory entry, spans as many sectors as it
    needs, nothing special about its placement.

    Entry format, back-to-back, no fixed width, repeated once per label:
        offset  size   field
        0       4      label's resolved address, u32 LE
        4       N      label name, ASCII, NUL-terminated (N = len+1)

    On collisions (two different files defining the same label name),
    the same last-one-wins rule used for cross-file linking applies, so
    the symbol file matches exactly what the linker actually resolved
    calls to -- not a raw dump of every file's separate label table.
"""

import sys
import os
import re
import argparse
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import x32sm  # noqa: E402  (local import after sys.path tweak)

SECTOR_SIZE = 1024          # must match Vars.DISK_SECTOR_SIZE
DISK_END_SECTOR = 524288    # must match Vars.DISK_END_SECTOR

BOOT_SECTOR = 0
EXT_BOOT_START_SECTOR = 1
EXT_BOOT_SECTOR_COUNT = 3
DIR_SECTOR = 4
FILES_START_SECTOR = 5

DIR_ENTRY_SIZE = 30
DIR_NAME_LEN = 20
DIR_MAX_ENTRIES = SECTOR_SIZE // DIR_ENTRY_SIZE  # 34
ENTRY_MAGIC = 0xFE
DESC_MAGIC = 0xFD

FIEX_SUBDIR = "com"
FIEX_FILENAME = ".fiex"


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------
# .fiex build-config parsing
# --------------------------------------------------------------------------

class FiexConfig:
    __slots__ = ("docompile", "sinboot", "extboot", "symfile", "ext_overrides")

    def __init__(self):
        self.docompile = None      # set[str], lowercased extensions incl. dot
        self.sinboot = None        # str, filename
        self.extboot = None        # str, filename
        self.symfile = None        # str, on-disk name
        self.ext_overrides = {}    # {filename: ".NEWEXT"}


_FIEX_DIRECTIVE_RE = re.compile(r"^(\w+)\s*\{(.*)\}\s*$")


def strip_fiex_comment(line):
    # `//` starts a comment to end of line. No escaping needed since
    # filenames/extensions in this format can't contain `//` themselves.
    idx = line.find("//")
    if idx != -1:
        line = line[:idx]
    return line


def parse_fiex(path):
    """Parses a .fiex file into a FiexConfig. Every directive is
    mandatory; missing ones are reported together in one error rather
    than one-at-a-time, so a person fixing their .fiex isn't stuck
    re-running the build for each individually missing line."""
    with open(path, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    config = FiexConfig()
    seen_docompile = False

    for line_no, raw_line in enumerate(raw_lines, start=1):
        line = strip_fiex_comment(raw_line).strip()
        if not line:
            continue

        m = _FIEX_DIRECTIVE_RE.match(line)
        if not m:
            die(f"{path}:{line_no}: malformed .fiex line: {raw_line.strip()!r} "
                f"(expected 'directive {{...}}')")

        directive, body = m.group(1), m.group(2)
        args = [a.strip() for a in body.split(",")]
        args = [a for a in args if a]  # drop empty pieces from stray commas

        if directive == "docompile":
            if not args:
                die(f"{path}:{line_no}: 'docompile' needs at least one extension")
            exts = set()
            for a in args:
                if not a.startswith("."):
                    die(f"{path}:{line_no}: 'docompile' extension {a!r} "
                        f"must start with '.' (e.g. '.x32')")
                exts.add(a.lower())
            config.docompile = exts
            seen_docompile = True

        elif directive == "sinboot":
            if len(args) != 1:
                die(f"{path}:{line_no}: 'sinboot' takes exactly one filename")
            config.sinboot = args[0]

        elif directive == "extboot":
            if len(args) != 1:
                die(f"{path}:{line_no}: 'extboot' takes exactly one filename")
            config.extboot = args[0]

        elif directive == "symfile":
            if len(args) != 1:
                die(f"{path}:{line_no}: 'symfile' takes exactly one name")
            config.symfile = args[0]

        elif directive == "ext":
            if len(args) != 2:
                die(f"{path}:{line_no}: 'ext' takes exactly two arguments: "
                    f"{{file, .NEWEXT}}")
            fname, new_ext = args
            if new_ext == "NoExt":
                new_ext = None  # sentinel: strip extension entirely, no dot
            elif not new_ext.startswith("."):
                die(f"{path}:{line_no}: 'ext' new extension {new_ext!r} "
                    f"must start with '.' (e.g. '.COM'), or be the literal "
                    f"keyword NoExt for no extension at all")
            if fname in config.ext_overrides:
                die(f"{path}:{line_no}: duplicate 'ext' override for "
                    f"{fname!r} (already set to "
                    f"{config.ext_overrides[fname]!r})")
            config.ext_overrides[fname] = new_ext

        else:
            die(f"{path}:{line_no}: unknown .fiex directive {directive!r}")

    missing = []
    if not seen_docompile:
        missing.append("docompile")
    if config.sinboot is None:
        missing.append("sinboot")
    if config.extboot is None:
        missing.append("extboot")
    if config.symfile is None:
        missing.append("symfile")
    if missing:
        die(f"{path}: missing required directive(s): {', '.join(missing)}")

    return config


def load_fiex_config(os_dir):
    fiex_path = os.path.join(os_dir, FIEX_SUBDIR, FIEX_FILENAME)
    if not os.path.isfile(fiex_path):
        die(f"build config not found: {fiex_path}\n"
            f"  every OS_DIR needs {FIEX_SUBDIR}/{FIEX_FILENAME} -- see "
            f"image.py's module docstring for the format")
    return parse_fiex(fiex_path)


# --------------------------------------------------------------------------
# Source discovery
# --------------------------------------------------------------------------

def is_source_file(fname, docompile_exts):
    return os.path.splitext(fname)[1].lower() in docompile_exts


def disk_name_for(fname, docompile_exts, ext_overrides):
    """kernel.asm -> KERNEL.BIN by default, or KERNEL.<override> if an
    `ext {}` directive names this exact file, or bare KERNEL (no dot at
    all) if that override is the NoExt keyword. Anything whose extension
    isn't in docompile_exts is copied as-is, name unchanged."""
    stem, ext = os.path.splitext(fname)
    if ext.lower() in docompile_exts:
        if fname in ext_overrides:
            new_ext = ext_overrides[fname]
            name = stem if new_ext is None else stem + new_ext
        else:
            name = stem + ".BIN"
    else:
        name = fname

    if len(name) > DIR_NAME_LEN:
        die(f"on-disk filename '{name}' (from '{fname}') is {len(name)} "
            f"bytes, exceeds the {DIR_NAME_LEN}-byte directory field limit")
    return name


def scan_os_dir(os_dir, boot_name, ext_boot_name):
    """Returns (boot_path, ext_boot_path, other_files) where other_files
    is a list of (fname, full_path) in os.listdir() order, excluding the
    boot/ext_boot files, excluding the com/ metadata subdirectory
    entirely, and excluding any other nested directories."""
    entries = os.listdir(os_dir)  # dir-listing order, per spec (not sorted)

    boot_path = None
    ext_boot_path = None
    others = []

    for fname in entries:
        if fname == FIEX_SUBDIR:
            continue  # com/ is metadata-only, never scanned as OS content

        full = os.path.join(os_dir, fname)
        if os.path.isdir(full):
            die(f"'{fname}' is a directory -- nested directories aren't "
                f"supported, OS_DIR must be flat (except for the "
                f"{FIEX_SUBDIR}/ metadata folder)")

        if fname == boot_name:
            boot_path = full
        elif fname == ext_boot_name:
            ext_boot_path = full
        else:
            others.append((fname, full))

    if boot_path is None:
        die(f"sinboot file '{boot_name}' (from .fiex) not found in {os_dir}")
    if ext_boot_path is None:
        die(f"extboot file '{ext_boot_name}' (from .fiex) not found in {os_dir}")

    return boot_path, ext_boot_path, others


def validate_ext_overrides(config, other_files):
    """Every `ext {file, .EXT}` must reference a real file in OS_DIR that
    is actually assembled (covered by docompile) -- checked up front so
    a typo'd filename fails fast with a clear message instead of the
    override silently never applying."""
    real_names = {fname for fname, _path in other_files}
    for fname, new_ext in config.ext_overrides.items():
        new_ext_display = "NoExt" if new_ext is None else new_ext
        if fname not in real_names:
            die(f".fiex 'ext {{{fname}, {new_ext_display}}}' references a file "
                f"that doesn't exist in the OS directory: {fname!r}")
        if not is_source_file(fname, config.docompile):
            ext = os.path.splitext(fname)[1]
            die(f".fiex 'ext {{{fname}, {new_ext}}}' references {fname!r}, "
                f"but its extension {ext!r} isn't in 'docompile', so it's "
                f"never assembled and has no output extension to override")


# --------------------------------------------------------------------------
# Two-pass cross-file assembly
# --------------------------------------------------------------------------

class AsmUnit:
    """One source file being tracked through the two build passes."""
    __slots__ = ("fname", "path", "disk_name", "labels", "exported_labels",
                 "local_labels", "code", "base_addr")

    def __init__(self, fname, path, disk_name=None):
        self.fname = fname
        self.path = path
        self.disk_name = disk_name  # None for boot/ext_boot (not "files")
        self.labels = {}
        self.exported_labels = {}
        self.local_labels = {}
        self.code = b""
        self.base_addr = 0


def read_source(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def assemble_pass1(unit):
    """Standalone label harvesting, no externs and no resolution -- other
    files' names this file references (e.g. kernel.asm calling
    sys_readfile) are expected to be unresolved at this stage; that's
    fixed up in pass 2 once every file's labels are known. Sources must
    set their own absolute address via `origin` (no --org offset is
    applied here -- there is no sector-based default, unlike the single
    file x32sm.py CLI, because these files' final position is decided by
    OS-level convention, not by disk layout)."""
    text = read_source(unit.path)
    try:
        (_code, _listing, labels, _base_addr,
         exported_labels, local_labels) = x32sm.assemble(
            text, org=0, collect_labels_only=True)
    except x32sm.AsmError as e:
        die(f"[{unit.fname}] pass 1 (label harvesting) failed: {e}")
    unit.labels = labels
    unit.exported_labels = exported_labels
    unit.local_labels = local_labels


def assemble_pass2(unit, all_units):
    """Real assembly, importing every OTHER unit's Pass 1 EXPORTED labels
    as externs (last-listed-wins on collision, same rule as x32sm.py's
    --import-symbols; order here is the same os.listdir() order used for
    disk placement, so builds are reproducible per machine). Uses
    exported_labels, not the full labels table, so a file with `global`
    lines only exposes what it explicitly marked -- a file with no
    `global` lines still exports everything (see x32sm.py's assemble()
    docstring), so old sources keep working unchanged."""
    externs = {}
    for other in all_units:
        if other is unit:
            continue
        externs.update(other.exported_labels)

    text = read_source(unit.path)
    try:
        (code, _listing, labels, base_addr,
         exported_labels, local_labels) = x32sm.assemble(
            text, org=0, extern_labels=externs)
    except x32sm.AsmError as e:
        die(f"[{unit.fname}] pass 2 assembly failed: {e}")
    unit.labels = labels
    unit.exported_labels = exported_labels
    unit.local_labels = local_labels
    unit.code = code
    unit.base_addr = base_addr


def build_all_units(boot_path, boot_name, ext_boot_path, ext_boot_name,
                     other_sources, docompile_exts, ext_overrides):
    """other_sources: list of (fname, full_path) for source files
    (already filtered from raw files by the caller, per docompile_exts)."""
    units = [AsmUnit(boot_name, boot_path)]
    units.append(AsmUnit(ext_boot_name, ext_boot_path))
    for fname, path in other_sources:
        disk_name = disk_name_for(fname, docompile_exts, ext_overrides)
        units.append(AsmUnit(fname, path, disk_name=disk_name))

    for u in units:
        assemble_pass1(u)

    for u in units:
        assemble_pass2(u, units)

    return units


# --------------------------------------------------------------------------
# Directory (sector 4) construction
# --------------------------------------------------------------------------

def build_directory_sector(entries):
    """entries: list of (disk_name, start_sector, length_sectors)."""
    if len(entries) > DIR_MAX_ENTRIES:
        die(f"too many files ({len(entries)}), directory sector holds "
            f"at most {DIR_MAX_ENTRIES}")

    buf = bytearray(SECTOR_SIZE)
    off = 0
    for name, start_sector, length_sectors in entries:
        if len(name) > DIR_NAME_LEN:
            die(f"on-disk filename '{name}' exceeds {DIR_NAME_LEN} bytes")
        name_bytes = name.encode("ascii") + b"\x00" * (DIR_NAME_LEN - len(name))

        buf[off] = ENTRY_MAGIC
        struct.pack_into("<I", buf, off + 1, start_sector)
        struct.pack_into("<I", buf, off + 5, length_sectors)
        buf[off + 9] = DESC_MAGIC
        buf[off + 10:off + 10 + DIR_NAME_LEN] = name_bytes
        off += DIR_ENTRY_SIZE
    # remaining bytes stay zero -> first unused entry's magic byte is 0x00,
    # which the OS-side parser treats as end-of-list
    return bytes(buf)


# --------------------------------------------------------------------------
# Symbol file construction
# --------------------------------------------------------------------------

def build_symbol_table(units):
    """Collects every unit's LOCAL label (name, address) pairs into one
    list -- NOT a dict merge, deliberately, because `global` lets
    different files reuse the same private label name (that's the whole
    point), so two files can easily define a same-named label at
    different addresses. A dict keyed by name would silently drop one of
    them; this keeps both. Uses u.local_labels (only what THIS file
    itself defines), NOT u.labels (which also contains every cross-file
    extern it imported) and NOT u.exported_labels (restricted by
    `global`) -- u.labels would duplicate each cross-file symbol once
    per importing file, since assemble() seeds externs into `labels`
    before collecting local defs; u.local_labels already excludes those
    passthrough entries. SYMBOLS.SYM is a debug/stack-trace aid, not a
    linking artifact, so it intentionally includes file-private labels
    too, unrestricted by `global`. Duplicate names across files are
    fine: the stack-trace lookup walks address-sorted entries picking
    the nearest one at or below a target address, which works correctly
    regardless of whether some names repeat. `units` should be [boot,
    ext_boot, *file_units] (build order, though order doesn't actually
    matter for this list)."""
    pairs = []
    for u in units:
        pairs.extend(u.local_labels.items())
    return pairs


def encode_symbol_file(symbol_pairs):
    """Binary format, repeated per label, no fixed width:
        offset 0  size 4  address, u32 LE
        offset 4  size N  ASCII name, NUL-terminated
    `symbol_pairs` is a list of (name, addr), NOT a dict -- duplicate
    names are expected and preserved (see build_symbol_table). Order: by
    address ascending, then name, so the file is stable/diffable across
    rebuilds instead of depending on collection order, and so the
    stack-trace-style nearest-at-or-below lookup can rely on ascending
    order and stop scanning early."""
    buf = bytearray()
    for name, addr in sorted(symbol_pairs, key=lambda kv: (kv[1], kv[0])):
        try:
            name_bytes = name.encode("ascii")
        except UnicodeEncodeError:
            die(f"symbol name '{name}' isn't ASCII, can't encode into the symbol file")
        buf += struct.pack("<I", addr)
        buf += name_bytes
        buf += b"\x00"
    return bytes(buf)


# --------------------------------------------------------------------------
# Build driver
# --------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(
        description="Builds a full VSK-32 disk image from a flat OS source directory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("os_dir", help="Flat directory containing every OS source/asset "
                                    "file, plus a com/.fiex build config")
    p.add_argument("-o", "--output", required=True, metavar="IMG",
                    help="Output disk image path")
    p.add_argument("--disk-size", type=int, default=512 * 1024 * 1024,
                    help="Size of the disk image in bytes if it doesn't already exist "
                         "(default 512MiB, matching vsk32env.py WriteVMDisk)")
    args = p.parse_args(argv)

    if not os.path.isdir(args.os_dir):
        die(f"not a directory: {args.os_dir}")

    config = load_fiex_config(args.os_dir)

    boot_path, ext_boot_path, other_files = scan_os_dir(
        args.os_dir, config.sinboot, config.extboot)

    validate_ext_overrides(config, other_files)

    other_sources = [(f, p_) for f, p_ in other_files
                      if is_source_file(f, config.docompile)]
    other_raw = [(f, p_) for f, p_ in other_files
                  if not is_source_file(f, config.docompile)]

    print(f"Boot loader:          {config.sinboot}")
    print(f"Extended boot loader: {config.extboot}")
    print(f"Symbol file:          {config.symfile}")
    print(f"docompile extensions: {', '.join(sorted(config.docompile))}")
    if config.ext_overrides:
        print(f"Extension overrides:  " +
              ", ".join(f"{f}->{'NoExt' if e is None else e}"
                         for f, e in config.ext_overrides.items()))
    print(f"OS source files:      {len(other_sources)}")
    print(f"Raw/asset files:      {len(other_raw)}")
    print()

    print("Pass 1/2: harvesting labels from every source file...")
    units = build_all_units(boot_path, config.sinboot,
                             ext_boot_path, config.extboot,
                             other_sources, config.docompile,
                             config.ext_overrides)
    boot_unit, ext_boot_unit = units[0], units[1]
    file_units = units[2:]
    print(f"  linked {len(units)} source file(s), "
          f"{sum(len(u.labels) for u in units)} total symbols visible")
    print()

    # --- boot sector: must fit in exactly 1 sector ---
    if len(boot_unit.code) > SECTOR_SIZE:
        die(f"'{config.sinboot}' assembled to {len(boot_unit.code)} bytes, "
            f"exceeds the {SECTOR_SIZE}-byte boot sector")
    boot_sector_data = boot_unit.code.ljust(SECTOR_SIZE, b"\x00")

    # --- extended boot loader: must fit in exactly 3 sectors ---
    ext_boot_max = SECTOR_SIZE * EXT_BOOT_SECTOR_COUNT
    if len(ext_boot_unit.code) > ext_boot_max:
        die(f"'{config.extboot}' assembled to {len(ext_boot_unit.code)} bytes, "
            f"exceeds the {ext_boot_max}-byte extended boot loader region "
            f"({EXT_BOOT_SECTOR_COUNT} sectors)")
    ext_boot_data = ext_boot_unit.code.ljust(ext_boot_max, b"\x00")

    # --- directory aliases for the boot loader / extended boot loader ---
    # These don't move or duplicate any bytes -- sector 0 and sectors 1-3
    # stay exactly where the BIOS/boot chain hardwire expects them. This
    # just ADDS directory entries so B_LOAD_FILE (or anything else that
    # reads the SSFS directory) can find and load them like any other
    # file. Naming is FIXED (stem + .BOOT) regardless of any `ext {}`
    # overrides, which only ever apply to regular OS_DIR files.
    dir_entries = []
    file_writes = []  # (byte_offset, data)

    def boot_alias_name_for(source_fname):
        stem, _ext = os.path.splitext(source_fname)
        name = stem + ".BOOT"
        if len(name) > DIR_NAME_LEN:
            die(f"on-disk filename '{name}' (from '{source_fname}') "
                f"exceeds the {DIR_NAME_LEN}-byte directory field limit")
        return name

    boot_alias_name = boot_alias_name_for(config.sinboot)
    dir_entries.append((boot_alias_name, BOOT_SECTOR, 1))

    ext_boot_alias_name = boot_alias_name_for(config.extboot)
    dir_entries.append((ext_boot_alias_name, EXT_BOOT_START_SECTOR,
                         EXT_BOOT_SECTOR_COUNT))

    print(f"  {boot_alias_name:<20} {SECTOR_SIZE:>8} B (boot alias)  "
          f"-> sector {BOOT_SECTOR} (unchanged)")
    print(f"  {ext_boot_alias_name:<20} {ext_boot_max:>8} B (ext_boot alias) "
          f"-> sectors {EXT_BOOT_START_SECTOR}..{EXT_BOOT_START_SECTOR + EXT_BOOT_SECTOR_COUNT - 1} (unchanged)")

    # --- lay out remaining files (assembled + raw), dir order ---
    cursor = FILES_START_SECTOR

    print("Packing files:")
    for u in file_units:
        data = u.code
        sectors_needed = (len(data) + SECTOR_SIZE - 1) // SECTOR_SIZE
        dir_entries.append((u.disk_name, cursor, sectors_needed))
        file_writes.append((cursor * SECTOR_SIZE, data))
        print(f"  {u.disk_name:<20} {len(data):>8} B (assembled)  "
              f"-> sectors {cursor}..{cursor + sectors_needed - 1}")
        cursor += sectors_needed

    for fname, path in other_raw:
        disk_name = disk_name_for(fname, config.docompile, config.ext_overrides)
        with open(path, "rb") as f:
            data = f.read()
        sectors_needed = (len(data) + SECTOR_SIZE - 1) // SECTOR_SIZE
        dir_entries.append((disk_name, cursor, sectors_needed))
        file_writes.append((cursor * SECTOR_SIZE, data))
        print(f"  {disk_name:<20} {len(data):>8} B (raw)         "
              f"-> sectors {cursor}..{cursor + sectors_needed - 1}")
        cursor += sectors_needed

    symfile_disk_name = disk_name_for(config.symfile, config.docompile, config.ext_overrides)
    symbol_table = build_symbol_table(units)  # every label, every unit
    data = encode_symbol_file(symbol_table)
    sectors_needed = (len(data) + SECTOR_SIZE - 1) // SECTOR_SIZE
    dir_entries.append((symfile_disk_name, cursor, sectors_needed))
    file_writes.append((cursor * SECTOR_SIZE, data))
    print(f"  {symfile_disk_name:<20} {len(data):>8} B (symbols, "
          f"{len(symbol_table)} labels) -> sectors {cursor}..{cursor + sectors_needed - 1}")
    cursor += sectors_needed
    print()

    directory_sector = build_directory_sector(dir_entries)

    total_sectors_needed = cursor
    if total_sectors_needed > DISK_END_SECTOR:
        die(f"image needs {total_sectors_needed} sectors, exceeds "
            f"DISK_END_SECTOR ({DISK_END_SECTOR})")

    # --- create or open the disk image ---
    if not os.path.isfile(args.output):
        needed_bytes = max(args.disk_size, total_sectors_needed * SECTOR_SIZE)
        with open(args.output, "wb") as f:
            f.write(b"\x00" * needed_bytes)
        print(f"Created new disk image: {args.output} ({needed_bytes} bytes)")
    else:
        existing_size = os.path.getsize(args.output)
        max_sectors = existing_size // SECTOR_SIZE
        if total_sectors_needed > max_sectors:
            die(f"existing disk image '{args.output}' has {max_sectors} "
                f"sectors, need {total_sectors_needed}. Delete it or pass "
                f"a larger --disk-size to recreate it.")

    with open(args.output, "r+b") as f:
        f.seek(BOOT_SECTOR * SECTOR_SIZE)
        f.write(boot_sector_data)

        f.seek(EXT_BOOT_START_SECTOR * SECTOR_SIZE)
        f.write(ext_boot_data)

        f.seek(DIR_SECTOR * SECTOR_SIZE)
        f.write(directory_sector)

        for byte_offset, data in file_writes:
            f.seek(byte_offset)
            f.write(data)

    print(f"Wrote {len(dir_entries)} file(s) + boot/ext_boot/directory "
          f"-> '{args.output}'")
    print(f"Next free sector: {cursor}")
    print()
    print(f"Next: python3 vsk32env.py LoadDiskImage {args.output}")
    print("(only needed if VM_DISK/vmdisk.img isn't this file already --")
    print(" image.py writes directly to the path you gave with -o, so")
    print(" if you passed -o VM_DISK/vmdisk.img you're already done.)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
