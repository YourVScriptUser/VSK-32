# System.py
 
# Local imports
from Emu.System.Dependencies import Teknikality
from Emu.System              import Vars
from Emu.Exceptions          import Exceptions
 
# Lib imports
import sys
import os
import time
import re
import keyboard
import traceback
import threading
import tkinter as tk
from tkinter import ttk, font as tkfont

# Check valid OS (Windows)
if os.name != "nt":
    raise OSError("Windows-only program.")
import ctypes

def emu_warn(msg):
    sys_write_stdout(f"{Teknikality.colors.YELLOW}WARNING: {Teknikality.colors.BRIGHT_BLACK}{msg}{Teknikality.colors.RESET}")
 
def sys_write_stdout(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()
 
def error_window(error_message, error_title='Application Error'):
      """blocking error window"""
      u_type = 0x0 | 0x10
      
      ctypes.windll.user32.MessageBoxW(0, f"{error_message}", error_title, u_type)
      sys.exit(0)
       
 
class DwordArray:
    """A helper object for 32-bit registers"""
    def __init__(self, slots):
        self.starting_slots     =       slots
        self.arr                =       [0] * slots
        self.max_index          =       len(self.arr) - 1 # minus 1 for zero-index
        self.mask               =       0xFFFFFFFF        # 32-bit integer limit
        self.size               =       len(self.arr)
 
    def write(self, val, arr=0):
 
        if not 0 <= arr <= self.max_index:
            raise Exceptions.InvalidRegister
       
        self.arr[arr] = (val & self.mask)
 
    def read(self, arr=0):
        if not 0 <= arr <= self.max_index:
            raise Exceptions.InvalidRegister
 
        return self.arr[arr]
 
    def clear(self):
        self.arr = [0] * self.starting_slots
 
    def increment(self, t=0, arr=0):
        if not 0 <= arr <= self.max_index:
            raise Exceptions.InvalidRegister
 
        current = self.read(arr=arr)
        current += 1 + t
 
        self.write(arr=arr, val=current)
 
    def decrement(self, t=0, arr=0):
        if not 0 <= arr <= self.max_index:
            raise Exceptions.InvalidRegister
 
        current = self.read(arr=arr)
        current -= 1 + t
 
        self.write(arr=arr, val=current)    
       
 
class registers:
 
    def __init__(self):
        self.regs32       = DwordArray(24) # 24 general-purpose 32-bit registers
        self.regs32_save  = DwordArray(24) # Register save slots for interrupts
        self.ip           = DwordArray(1)  # 32-bit instruction pointer
        self.flags        = {
            "EQ": 0,                       # Comparison was equal
            "HI": 0,                       # First register was higher
            "LO": 0,                       # First register was lower
            "IF": 0                        # Interrupt flag, 1=on, 0=off.
 
        }
        self.sp           = DwordArray(1)  # Stack initialized to 0x00000000

           
 
class memory:
    MEM_SIZE = 256 * 1024 * 1024
    MAX_ADDR = 0x0FFFFFFF
    class Map:
        """
        Class for resolving address regions in memory
        All formatted *[end, start]* in a **list**
        """
        IVT         = [0x00000000, 0x000000FF]         # Not really used anywhere since IVT indexing is done via bytes, which cannot physically go above 0xFF
        VIDEO       = [0x00000000, 0x00000000]         # Set by Display.py so we don't need to add circular importing errors
        # ADDITION: MMIO is no longer hardcoded, done using port registers        # Nice lil x86 throwback
        # Memory protection has been removed as it bought performance down to the HZ
       
    def __init__(self):
        self.Memory = bytearray(self.MEM_SIZE)    

    # ----------------
    # Read operations
    # ----------------
   
    def read_byte(self, addr):
        if addr > self.MAX_ADDR:
            raise Exceptions.InvalidMemoryWrite
        return self.Memory[addr]
 
    def read_word(self, addr):
        if addr > self.MAX_ADDR:
            raise Exceptions.InvalidMemoryWrite        
        return (
            self.Memory[addr]
            | (self.Memory[addr + 1] << 8)
        )
 
    def read_dword(self, addr):
        if addr > self.MAX_ADDR:
            raise Exceptions.InvalidMemoryWrite        
        return (
            self.Memory[addr]
            | (self.Memory[addr + 1] << 8)
            | (self.Memory[addr + 2] << 16)
            | (self.Memory[addr + 3] << 24)
        )
 
    # -----------------
    # Write operations
    # -----------------
 
    def write_byte(self, addr, val):
        if addr > self.MAX_ADDR:
            raise Exceptions.InvalidMemoryWrite        
        self.Memory[addr] = val & 0xFF
 
    def write_word(self, addr, val):                                                                                                                                          
        if addr > self.MAX_ADDR:
            raise Exceptions.InvalidMemoryWrite        
        self.Memory[addr]     = val & 0xFF
        self.Memory[addr + 1] = (val >> 8) & 0xFF
 
    def write_dword(self, addr, val):
        if addr > self.MAX_ADDR:
            raise Exceptions.InvalidMemoryWrite        
        self.Memory[addr]     = val & 0xFF
        self.Memory[addr + 1] = (val >> 8) & 0xFF
        self.Memory[addr + 2] = (val >> 16) & 0xFF
        self.Memory[addr + 3] = (val >> 24) & 0xFF

def format_hex_16(val):
    return f"{val:04x}"
 
def format_hex_8(val):
    return f"{val:02x}"
 
def format_hex_32(val):
    return f"{val:08x}"


class GUI:
    """Live debugger GUI. Runs in its own thread with its own Tk mainloop."""

    REFRESH_MS = 66         # register/flag/top-bar redraw cadence (cheap, stays snappy)
    HEX_REFRESH_MS = 150    # hex dump redraw cadence (expensive, deliberately slower)
    HZ_SAMPLE_MS = 250      # clock-speed sampling cadence (smoothed over a bigger window)
    FOLLOW_MARGIN = 32      # bytes of headroom before auto-recentre kicks in when following IP
    STACK_PEEK_DWORDS_EACH_SIDE = 8  # 8 dwords above + 8 below SP = 64 bytes total

    def __init__(self, regs: 'registers', mem: 'memory', cpu):
        self.regs = regs
        self.mem = mem
        self.cpu = cpu  # cpu32 class — reads cpu.current_cycle
        self.lock = threading.Lock()  # guards regs32/flags/ip/sp reads vs CPU writes

        self._thread = None
        self._stop = False
        self._paused = False  # pauses GUI redraw only, never touches the CPU thread

        # hex view range
        self.range_start = 0x00000000
        self.range_end = 0x000000FF
        self._last_dump_bytes = None
        self._last_ip_row_addr = None   # tracks IP separately so we redraw on IP move even if bytes are static
        self._hex_dirty = True          # forces a hex redraw next tick without needing a content compare
        self._follow_ip = True          # auto-recentres the hex view as IP moves

        # clock speed sampling state
        self._last_cycle_count = 0
        self._last_cycle_time = time.monotonic()
        self._current_hz = 0.0

        # register delta highlighting
        self._prev_reg_vals = [None] * self.regs.regs32.size

        # SP-relative stack peek
        self._last_sp_seen = None

    # ------------------------------------------------------------------
    # Public control
    # ------------------------------------------------------------------

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True

    # ------------------------------------------------------------------
    # Tk setup (runs inside GUI thread)
    # ------------------------------------------------------------------

    def _run(self):
        self.root = tk.Tk()
        self.root.title("Emu — Live Debugger")
        self.root.configure(bg="#1e1f22")
        self.root.geometry("1040x760")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.mono = tkfont.Font(family="Consolas", size=10)
        self.mono_bold = tkfont.Font(family="Consolas", size=10, weight="bold")
        self.mono_large = tkfont.Font(family="Consolas", size=13, weight="bold")

        self._build_style()
        self._build_layout()

        self._schedule_refresh()
        self._schedule_hex_refresh()
        self._schedule_hz_sample()

        self.root.mainloop()

    def _on_close(self):
        self._stop = True
        self.root.destroy()

    def _build_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        bg = "#1e1f22"
        panel = "#26272b"
        topbar = "#202124"
        fg = "#d4d4d4"
        accent = "#569cd6"

        style.configure("TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("Top.TFrame", background=topbar)
        style.configure("TLabel", background=bg, foreground=fg, font=self.mono)
        style.configure("Panel.TLabel", background=panel, foreground=fg, font=self.mono)
        style.configure("Top.TLabel", background=topbar, foreground=fg, font=self.mono)
        style.configure("Header.TLabel", background=bg, foreground=accent, font=self.mono_bold)
        style.configure("Flag.TLabel", background=panel, foreground="#6a9955", font=self.mono_bold)
        style.configure("FlagOff.TLabel", background=panel, foreground="#5a5a5a", font=self.mono)
        style.configure("TEntry", fieldbackground=panel, foreground=fg, insertcolor=fg)
        style.configure("TButton", background="#333", foreground=fg)
        style.configure("HzValue.TLabel", background=topbar, foreground="#4ec9b0", font=self.mono_large)
        style.configure("RegChanged.TLabel", background=panel, foreground="#ffffff", font=self.mono_bold)
        style.configure("RegNormal.TLabel", background=panel, foreground="#ce9178", font=self.mono)

        self.colors = dict(bg=bg, panel=panel, topbar=topbar, fg=fg, accent=accent)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self):
        root = self.root

        # ---- Top bar: clock speed / cycle count / view controls ----
        topbar = ttk.Frame(root, style="Top.TFrame", padding=(14, 8))
        topbar.pack(fill="x", side="top")

        ttk.Label(topbar, text="CLOCK", style="Top.TLabel").pack(side="left")
        self.hz_var = tk.StringVar(value="0 Hz")
        ttk.Label(topbar, textvariable=self.hz_var, style="HzValue.TLabel").pack(side="left", padx=(6, 24))

        ttk.Label(topbar, text="CYCLES", style="Top.TLabel").pack(side="left")
        self.cycle_var = tk.StringVar(value="0")
        ttk.Label(topbar, textvariable=self.cycle_var, style="Top.TLabel", foreground="#ce9178").pack(side="left", padx=(6, 24))

        self.follow_btn = ttk.Button(topbar, text="Follow IP: On", command=self._toggle_follow)
        self.follow_btn.pack(side="left", padx=(0, 8))

        self.pause_btn = ttk.Button(topbar, text="Pause View", command=self._toggle_pause)
        self.pause_btn.pack(side="right")

        outer = ttk.Frame(root, padding=10)
        outer.pack(fill="both", expand=True)

        # ---- Left column: registers / flags / ip / sp / stack peek ----
        left = ttk.Frame(outer, style="Panel.TFrame", padding=10)
        left.pack(side="left", fill="y", padx=(0, 10))

        ttk.Label(left, text="REGISTERS", style="Header.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))

        self.reg_vars = []
        self.reg_labels = []
        n_regs = self.regs.regs32.size
        cols = 2
        for i in range(n_regs):
            r, cidx = divmod(i, cols)
            name_lbl = ttk.Label(left, text=f"R{i:<2}", style="Panel.TLabel")
            name_lbl.grid(row=r + 1, column=cidx * 2, sticky="w", padx=(0, 4), pady=1)
            val = tk.StringVar(value="00000000")
            val_lbl = ttk.Label(left, textvariable=val, style="RegNormal.TLabel")
            val_lbl.grid(row=r + 1, column=cidx * 2 + 1, sticky="w", padx=(0, 14), pady=1)
            self.reg_vars.append(val)
            self.reg_labels.append(val_lbl)

        sep_row = (n_regs // cols) + 2
        ttk.Separator(left, orient="horizontal").grid(row=sep_row, column=0, columnspan=4, sticky="ew", pady=8)

        # IP / SP
        ttk.Label(left, text="IP", style="Panel.TLabel").grid(row=sep_row + 1, column=0, sticky="w")
        self.ip_var = tk.StringVar(value="00000000")
        ttk.Label(left, textvariable=self.ip_var, style="Panel.TLabel", foreground="#4ec9b0").grid(row=sep_row + 1, column=1, sticky="w")

        ttk.Label(left, text="SP", style="Panel.TLabel").grid(row=sep_row + 1, column=2, sticky="w")
        self.sp_var = tk.StringVar(value="00000000")
        ttk.Label(left, textvariable=self.sp_var, style="Panel.TLabel", foreground="#4ec9b0").grid(row=sep_row + 1, column=3, sticky="w")

        ttk.Separator(left, orient="horizontal").grid(row=sep_row + 2, column=0, columnspan=4, sticky="ew", pady=8)

        # Flags
        ttk.Label(left, text="FLAGS", style="Header.TLabel").grid(row=sep_row + 3, column=0, columnspan=4, sticky="w", pady=(0, 6))

        self.flag_labels = {}
        flag_names = list(self.regs.flags.keys())
        for i, fname in enumerate(flag_names):
            lbl = ttk.Label(left, text=fname, style="FlagOff.TLabel")
            lbl.grid(row=sep_row + 4 + i, column=0, columnspan=4, sticky="w", pady=1)
            self.flag_labels[fname] = lbl

        # Stack peek (SP-relative)
        stack_row = sep_row + 4 + len(flag_names)
        ttk.Separator(left, orient="horizontal").grid(row=stack_row, column=0, columnspan=4, sticky="ew", pady=8)

        ttk.Label(left, text="STACK (SP-relative)", style="Header.TLabel").grid(
            row=stack_row + 1, column=0, columnspan=4, sticky="w", pady=(0, 6)
        )

        self.stack_text = tk.Text(
            left,
            bg="#1a1a1a",
            fg="#d4d4d4",
            font=self.mono,
            wrap="none",
            state="disabled",
            borderwidth=0,
            highlightthickness=0,
            height=self.STACK_PEEK_DWORDS_EACH_SIDE * 2 + 1,
            width=26,
        )
        self.stack_text.grid(row=stack_row + 2, column=0, columnspan=4, sticky="w")

        self.stack_text.tag_configure("offset", foreground="#569cd6")
        self.stack_text.tag_configure("sp_row", background="#3f2d2d", foreground="#ffffff")

        # ---- Right column: hex dump ----
        right = ttk.Frame(outer, style="Panel.TFrame", padding=10)
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(right, text="MEMORY VIEW", style="Header.TLabel").pack(anchor="w", pady=(0, 6))

        controls = ttk.Frame(right, style="Panel.TFrame")
        controls.pack(fill="x", pady=(0, 6))

        ttk.Label(controls, text="Start:", style="Panel.TLabel").pack(side="left")
        self.start_entry = ttk.Entry(controls, width=12, font=self.mono)
        self.start_entry.insert(0, f"{self.range_start:08X}")
        self.start_entry.pack(side="left", padx=(4, 12))

        ttk.Label(controls, text="End:", style="Panel.TLabel").pack(side="left")
        self.end_entry = ttk.Entry(controls, width=12, font=self.mono)
        self.end_entry.insert(0, f"{self.range_end:08X}")
        self.end_entry.pack(side="left", padx=(4, 12))

        go_btn = ttk.Button(controls, text="Go", command=self._apply_range)
        go_btn.pack(side="left")

        ip_btn = ttk.Button(controls, text="Jump to IP", command=self._jump_to_ip)
        ip_btn.pack(side="left", padx=(8, 0))

        self.range_error_var = tk.StringVar(value="")
        ttk.Label(controls, textvariable=self.range_error_var, style="Panel.TLabel", foreground="#f14c4c").pack(side="left", padx=(12, 0))

        # Quick-range buttons — saves retyping addresses for common regions
        quick_ranges = ttk.Frame(right, style="Panel.TFrame")
        quick_ranges.pack(fill="x", pady=(0, 6))

        ttk.Label(quick_ranges, text="Quick jump:", style="Panel.TLabel").pack(side="left", padx=(0, 8))

        ttk.Button(quick_ranges, text="IVT",
                   command=lambda: self._quick_range(*self.mem.Map.IVT)).pack(side="left", padx=(0, 4))
        ttk.Button(quick_ranges, text="Video",
                   command=lambda: self._quick_range(*self.mem.Map.VIDEO)).pack(side="left", padx=(0, 4))
        ttk.Button(quick_ranges, text="IP ±2K",
                   command=self._jump_to_ip).pack(side="left", padx=(0, 4))
        ttk.Button(quick_ranges, text="SP ±2K",
                   command=self._quick_range_around_sp).pack(side="left", padx=(0, 4))
        ttk.Button(quick_ranges, text="Start of mem",
                   command=lambda: self._quick_range(0x00000000, 0x00000FFF)).pack(side="left", padx=(0, 4))
        ttk.Button(quick_ranges, text="Next 4K →",
                   command=self._quick_range_next_page).pack(side="left", padx=(0, 4))

        # Hex dump text widget (hex + ascii drawn as one monospace block)
        text_frame = ttk.Frame(right)
        text_frame.pack(fill="both", expand=True)

        self.hex_text = tk.Text(
            text_frame,
            bg="#1a1a1a",
            fg="#d4d4d4",
            insertbackground="#d4d4d4",
            font=self.mono,
            wrap="none",
            state="disabled",
            borderwidth=0,
            highlightthickness=0,
        )
        scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.hex_text.yview)
        self.hex_text.configure(yscrollcommand=scroll.set)
        self.hex_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.hex_text.tag_configure("offset", foreground="#569cd6")
        self.hex_text.tag_configure("ascii", foreground="#6a9955")
        self.hex_text.tag_configure("ip_row", background="#2d3f2d")

    # ------------------------------------------------------------------
    # Range handling
    # ------------------------------------------------------------------

    def _apply_range(self, from_follow=False):
        try:
            start = int(self.start_entry.get(), 16)
            end = int(self.end_entry.get(), 16)
        except ValueError:
            self.range_error_var.set("Invalid hex")
            return

        if start > end:
            self.range_error_var.set("Start > End")
            return

        # if start == end (e.g. only one address was typed / pasted), treat
        # it as "give me a 4KB page starting here" rather than a zero-length range
        if start == end:
            end = min(start + 4096, self.mem.MAX_ADDR)
            self.end_entry.delete(0, "end")
            self.end_entry.insert(0, f"{end:08X}")

        max_addr = self.mem.MAX_ADDR
        if start > max_addr or end > max_addr:
            self.range_error_var.set("Out of bounds")
            return

        MAX_VIEW_BYTES = 0x4000  # 16KB per view cap, keeps redraw/compare cost bounded
        if end - start + 1 > MAX_VIEW_BYTES:
            end = start + MAX_VIEW_BYTES - 1
            self.end_entry.delete(0, "end")
            self.end_entry.insert(0, f"{end:08X}")
            self.range_error_var.set(f"Capped to {MAX_VIEW_BYTES} bytes")
        else:
            self.range_error_var.set("")

        self.range_start = start
        self.range_end = end
        self._hex_dirty = True

        # manually editing the range turns off auto-follow; the internal
        # auto-recentre path (from_follow=True) leaves it untouched
        if not from_follow:
            self._follow_ip = False
            self.follow_btn.configure(text="Follow IP: Off")

    def _quick_range(self, start, end):
        """Sets the Start/End entry boxes and applies the range. Used by
        quick-select buttons for known regions (IVT, Video, etc)."""
        self.start_entry.delete(0, "end")
        self.start_entry.insert(0, f"{start:08X}")
        self.end_entry.delete(0, "end")
        self.end_entry.insert(0, f"{end:08X}")
        self._apply_range()

    def _quick_range_around_sp(self):
        with self.lock:
            sp_val = self.regs.sp.read()

        start = max(sp_val - 0x800, 0)
        end = min(start + 0x1000, self.mem.MAX_ADDR)
        self._quick_range(start, end)

    def _quick_range_next_page(self):
        """Advances the current view forward by its own width — a quick way
        to page through memory without retyping addresses each time."""
        width = self.range_end - self.range_start + 1
        start = min(self.range_end + 1, self.mem.MAX_ADDR)
        end = min(start + width - 1, self.mem.MAX_ADDR)
        self._quick_range(start, end)

    def _jump_to_ip(self):
        with self.lock:
            ip_val = self.regs.ip.read()

        width = max(self.range_end - self.range_start, 0xFF)
        start = max(ip_val - width // 4, 0)
        end = min(start + width, self.mem.MAX_ADDR)

        self.start_entry.delete(0, "end")
        self.start_entry.insert(0, f"{start:08X}")
        self.end_entry.delete(0, "end")
        self.end_entry.insert(0, f"{end:08X}")

        self._apply_range(from_follow=True)
        self._follow_ip = True
        self.follow_btn.configure(text="Follow IP: On")

    def _toggle_follow(self):
        self._follow_ip = not self._follow_ip
        self.follow_btn.configure(text=f"Follow IP: {'On' if self._follow_ip else 'Off'}")
        if self._follow_ip:
            self._jump_to_ip()

    def _toggle_pause(self):
        self._paused = not self._paused
        self.pause_btn.configure(text="Resume View" if self._paused else "Pause View")

    # ------------------------------------------------------------------
    # Clock speed sampling
    # ------------------------------------------------------------------

    def _schedule_hz_sample(self):
        if self._stop:
            return
        self._sample_hz()
        self.root.after(self.HZ_SAMPLE_MS, self._schedule_hz_sample)

    def _sample_hz(self):
        now = time.monotonic()
        cycle_now = self.cpu.current_cycle  # plain int read, no lock needed

        dt = now - self._last_cycle_time
        d_cycles = cycle_now - self._last_cycle_count

        if dt > 0:
            self._current_hz = d_cycles / dt

        self._last_cycle_time = now
        self._last_cycle_count = cycle_now

    @staticmethod
    def _format_hz(hz):
        if hz >= 1_000_000:
            return f"{hz / 1_000_000:.2f} MHz"
        elif hz >= 1_000:
            return f"{hz / 1_000:.2f} kHz"
        else:
            return f"{hz:.0f} Hz"

    # ------------------------------------------------------------------
    # Fast refresh: registers / flags / top bar / stack peek trigger
    # (runs every REFRESH_MS)
    # ------------------------------------------------------------------

    def _schedule_refresh(self):
        if self._stop:
            return
        if not self._paused:
            self._refresh_registers()
        self.root.after(self.REFRESH_MS, self._schedule_refresh)

    def _refresh_registers(self):
        with self.lock:
            reg_vals = list(self.regs.regs32.arr)
            ip_val = self.regs.ip.read()
            sp_val = self.regs.sp.read()
            flags = dict(self.regs.flags)

        cycle_now = self.cpu.current_cycle

        # registers + delta highlight: flash white the tick a value changes,
        # fall back to normal color the next tick it's unchanged
        for i, val in enumerate(reg_vals):
            self.reg_vars[i].set(f"{val:08X}")

            prev = self._prev_reg_vals[i]
            if prev is not None and val != prev:
                self.reg_labels[i].configure(style="RegChanged.TLabel")
            else:
                self.reg_labels[i].configure(style="RegNormal.TLabel")
        self._prev_reg_vals = reg_vals

        self.ip_var.set(f"{ip_val:08X}")
        self.sp_var.set(f"{sp_val:08X}")

        for fname, lbl in self.flag_labels.items():
            if flags.get(fname):
                lbl.configure(text=f"{fname} ●", style="Flag.TLabel")
            else:
                lbl.configure(text=f"{fname} ○", style="FlagOff.TLabel")

        self.hz_var.set(self._format_hz(self._current_hz))
        self.cycle_var.set(f"{cycle_now:,}")

        # stack peek follows SP automatically — only re-render when it moves
        if sp_val != self._last_sp_seen:
            self._last_sp_seen = sp_val
            self._render_stack_peek(sp_val)

        # auto-follow: recentre the hex view if IP has drifted near the edge
        # of (or outside) the visible window. Cheap integer math only —
        # the actual memory read/redraw happens later in _refresh_hex.
        if self._follow_ip:
            span = self.range_end - self.range_start
            near_low = ip_val < self.range_start + self.FOLLOW_MARGIN
            near_high = ip_val > self.range_end - self.FOLLOW_MARGIN
            if ip_val < self.range_start or ip_val > self.range_end or near_low or near_high:
                width = max(span, 0xFF)
                start = max(ip_val - width // 4, 0)
                end = min(start + width, self.mem.MAX_ADDR)
                self.range_start, self.range_end = start, end
                self.start_entry.delete(0, "end")
                self.start_entry.insert(0, f"{start:08X}")
                self.end_entry.delete(0, "end")
                self.end_entry.insert(0, f"{end:08X}")
                self._hex_dirty = True

        # IP moved to a new row -> hex dump needs a redraw even if the
        # underlying bytes in view are unchanged
        if ip_val != self._last_ip_row_addr:
            self._last_ip_row_addr = ip_val
            self._hex_dirty = True

    # ------------------------------------------------------------------
    # Stack peek — small fixed-width window around SP, rendered separately
    # from the main hex dump so SP doesn't need to be retyped into the
    # range box every time it moves.
    # ------------------------------------------------------------------

    def _render_stack_peek(self, sp_val):
        span = self.STACK_PEEK_DWORDS_EACH_SIDE * 4
        start = max(sp_val - span, 0)
        end = min(sp_val + span + 3, self.mem.MAX_ADDR)  # +3 to complete the final dword

        try:
            data = bytes(self.mem.Memory[start:end + 1])
        except Exception:
            return

        self.stack_text.configure(state="normal")
        self.stack_text.delete("1.0", "end")

        for row_off in range(0, len(data), 4):
            addr = start + row_off
            dword_bytes = data[row_off:row_off + 4]
            hex_part = " ".join(f"{b:02X}" for b in dword_bytes)

            row_start = self.stack_text.index("end-1c")
            self.stack_text.insert("end", f"{addr:08X}  ", "offset")
            self.stack_text.insert("end", f"{hex_part}\n")

            if addr <= sp_val < addr + 4:
                row_end = self.stack_text.index("end-1c")
                self.stack_text.tag_add("sp_row", row_start, row_end)

        self.stack_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Slow refresh: hex dump (runs every HEX_REFRESH_MS)
    #
    # Always does a bounded compare (max MAX_VIEW_BYTES, i.e. <=16KB) of the
    # current view's bytes against the last render, regardless of whether
    # IP/range-driven flags marked it dirty. This is what catches memory
    # changing under a static view — e.g. watching the keyboard buffer while
    # IP sits elsewhere. Bounded by view width, so it stays cheap even on a
    # busy CPU thread — no full re-render happens unless bytes genuinely differ.
    # ------------------------------------------------------------------

    def _schedule_hex_refresh(self):
        if self._stop:
            return
        if not self._paused:
            self._refresh_hex()
        self.root.after(self.HEX_REFRESH_MS, self._schedule_hex_refresh)

    def _refresh_hex(self):
        start, end = self.range_start, self.range_end
        length = end - start + 1

        try:
            data = bytes(self.mem.Memory[start:start + length])
        except Exception:
            return

        content_changed = (data != self._last_dump_bytes)

        if not content_changed and not self._hex_dirty:
            return

        self._last_dump_bytes = data
        self._hex_dirty = False

        ip_val = self._last_ip_row_addr if self._last_ip_row_addr is not None else -1

        lines = []
        bytes_per_row = 16
        for row_off in range(0, length, bytes_per_row):
            row_bytes = data[row_off:row_off + bytes_per_row]
            addr = start + row_off

            hex_part = " ".join(f"{b:02X}" for b in row_bytes)
            hex_part = hex_part.ljust(bytes_per_row * 3 - 1)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in row_bytes)
            is_ip_row = addr <= ip_val < addr + bytes_per_row

            lines.append((f"{addr:08X}", hex_part, ascii_part, is_ip_row))

        # remember scroll position so redraw doesn't jump the view to the top
        yview_before = self.hex_text.yview()

        self.hex_text.configure(state="normal")
        self.hex_text.delete("1.0", "end")

        for addr_str, hex_part, ascii_part, is_ip_row in lines:
            row_start = self.hex_text.index("end-1c")
            self.hex_text.insert("end", f"{addr_str}  ", "offset")
            self.hex_text.insert("end", f"{hex_part}  ")
            self.hex_text.insert("end", f"|{ascii_part}|\n", "ascii")
            if is_ip_row:
                row_end = self.hex_text.index("end-1c")
                self.hex_text.tag_add("ip_row", row_start, row_end)

        self.hex_text.configure(state="disabled")
        self.hex_text.yview_moveto(yview_before[0])


def start_gui(regs: 'registers', mem: 'memory', cpu) -> GUI:
    """Spins up the live debugger GUI in a background thread and returns the handle.

    cpu should be the cpu32 class (or any object exposing .current_cycle as an int)."""
    gui = GUI(regs, mem, cpu)
    gui.start()
    return gui





        
        
            
            







