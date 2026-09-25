# vibe coded and copied verbatim from claude

"""
gui_display.py

DearPyGui port of the terminal video-refresh loop. Same memory-walk logic
as the original (read VIDEO_START/END ports, walk memref byte-by-byte,
treat 10-126 as printable chars and specific bytes as color switches,
handle the blinking cursor), but instead of building an ANSI string and
writing it to stdout, it builds colored text runs and draws them into a
DearPyGui window using a retro 8x8 bitmap font.

Usage (mirrors your original spawn_refresh_thread pattern):

    from gui_display import GuiDisplay

    disp = GuiDisplay(mem, ports, cols=80, rows=25,
                       font_path="PxPlus_IBM_VGA8.ttf", font_size=8)
    t = disp.spawn_refresh_thread()   # builds the window AND runs it
    disp.can_refresh = True
    t.start()
    t.join()                          # blocks until the window is closed

Font note: DearPyGui loads real font FILES (ttf/otf) at a pixel size, it
doesn't ship an 8x8 terminal font itself. For the authentic blocky look,
grab a public-domain 8x8 bitmap font like "Px437_IBM_VGA8.ttf" or
"PxPlus_IBM_VGA8.ttf" (e.g. from int10h.org's "VGA text mode fonts"
pack, CC0/public domain) and pass its path as font_path. If you don't
pass one, GuiDisplay falls back to DPG's built-in default font so the
window still runs.
"""

import time
import threading
import queue

import dearpygui.dearpygui as dpg

# The Emu imports are only needed for the real memref/ports-driven path
# (_collect_frame_runs / spawn_refresh_thread). They're deferred so this
# file can still build the window and run feed_text()/the smoke test even
# if your Emu package isn't on the path yet. If you DID mean to use the
# real emulator path and nothing pops up, this is your first suspect:
# check the terminal for an ImportError from these two lines.
try:
    from Emu.System import System
    from Emu.System import SuperIO
except ImportError:
    System = None
    SuperIO = None


# ---- Color mapping -------------------------------------------------------
# The terminal version mapped these bytes to ANSI escape strings and let
# the terminal interpret them. A GUI window can't interpret ANSI escapes
# sitting inside a text string, so we map the same byte values straight to
# RGBA tuples instead. Adjust these to taste / to match your existing
# System.Teknikality.colors palette.
COLOR_MAP = {
    130: (255, 70, 70, 255),     # RED
    131: (70, 220, 70, 255),     # GREEN
    132: (90, 140, 255, 255),    # BLUE
    133: (120, 120, 120, 255),   # BRIGHT_BLACK
    134: (70, 220, 220, 255),    # CYAN
    136: (220, 220, 220, 255),   # RESET (also clears any active background - see below)
}
# Background-setting bytes are tracked separately from foreground ones:
# in real ANSI, fg and bg are independent channels, so setting a background
# shouldn't change whatever foreground color is currently active. dpg.add_text
# has no background fill at all (Dear ImGui just draws colored glyphs), so
# these runs get rendered as themed buttons instead - see _get_bg_theme().
BG_COLOR_MAP = {
    135: (150, 20, 20, 255),     # BG_RED
}
RESET_BYTE = 136
DEFAULT_COLOR = (220, 220, 220, 255)
CURSOR_COLOR = (220, 220, 220, 255)
CURSOR_GLYPH_BLOCK = "\u2582"  # ▂ - needs a font with block-element glyphs loaded
CURSOR_GLYPH_ASCII = "_"       # safe fallback for DPG's default font


def wrap_to_width(lines, width):
    """Identical to your original helper: hard-wrap each line to `width`."""
    wrapped = []
    for line in lines:
        if line == "":
            wrapped.append("")
        else:
            for i in range(0, len(line), width):
                wrapped.append(line[i:i + width])
    return wrapped


class GuiDisplay:
    def __init__(self, mem=None, ports=None,
                 cols: int = 80, rows: int = 25,
                 font_path: str = None, font_size: int = 8,
                 window_title: str = "Video Display",
                 capture_keyboard: bool = True):
        self.memref = mem
        self.prtref = ports

        self.can_refresh = False
        self.last_frame = ""
        self.threadExit = False
        self.start_time = time.monotonic()
        self.cursor_flag = False

        # cols/rows are recomputed from the real viewport size every
        # refresh once the window exists (see _sync_dimensions_to_viewport)
        # - these are just the starting values used to size the viewport
        # itself and as a fallback before that first resize.
        self.cols = cols
        self.rows = rows
        self.font_size = font_size
        self.font_path = font_path
        self.window_title = window_title
        self.capture_keyboard = capture_keyboard

        # '_' looks fine either way, so just always use it - no need to
        # special-case the block glyph based on whether a custom font with
        # block-element ranges got loaded.
        self.cursor_glyph = CURSOR_GLYPH_ASCII

        self._window_tag = "gui_display_window"
        self._text_tag = "gui_display_text_group"
        self._font_tag = None
        self._theme_tag = None
        self._bg_theme_cache = {}  # (fg, bg) tuple -> theme tag, see _get_bg_theme

        self._key_queue = queue.Queue()
        # Caps Lock is a TOGGLE, not a held modifier - dpg.is_key_down()
        # only reports "is this key physically down right now", which for
        # Caps Lock is true for a brief instant on press and tells you
        # nothing about the lock state afterward. DPG doesn't expose OS
        # lock-key state either, so we track the toggle ourselves: flip
        # this on every Caps Lock keypress instead of trying to query it.
        self._caps_lock = False
        # Repeat suppression: add_key_press_handler fires repeatedly while
        # a key is held (same as OS key-repeat), which is normally what
        # you want for typing. If you only want ONE event per physical
        # press, track down-state per key here instead - not done by
        # default since msvcrt.getch() behaved the same way (repeats while
        # held), matching the original terminal version's behavior.

    # ---- GUI construction ------------------------------------------------
    # IMPORTANT: DearPyGui wants every dpg.* call made from the thread that
    # created the context. spawn_refresh_thread() below calls this for you
    # from inside the same thread that later renders frames, so in the
    # normal (Emulator.py) usage you should NOT call this yourself. It's
    # only exposed for the single-threaded __main__ smoke test at the
    # bottom of this file.
    def build(self):
        dpg.create_context()

        with dpg.font_registry():
            if self.font_path:
                with dpg.font(self.font_path, self.font_size) as f:
                    pass  # Now automatic
                self._font_tag = f

        # Tight, terminal-like row spacing: DPG's default ItemSpacing puts
        # several extra pixels between every dpg.group() line, which is
        # what was making the line height look bloated. Zero it out and
        # keep just a hair of horizontal room between color-run chunks.
        with dpg.theme() as self._theme_tag:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 0, 0, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 4, 4, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0, category=dpg.mvThemeCat_Core)
                # DPG's default theme background is a mid gray, which reads
                # way too bright next to a retro-terminal color palette.
                # Push it down to near-black instead.
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (10, 10, 10, 255), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (10, 10, 10, 255), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_PopupBg, (10, 10, 10, 255), category=dpg.mvThemeCat_Core)

        with dpg.window(label=self.window_title, tag=self._window_tag,
                         no_scrollbar=True, no_collapse=True):
            dpg.add_group(tag=self._text_tag)

            if self.capture_keyboard:
                # NOTE: the previous approach used a hidden dpg.add_input_text
                # box plus dpg.focus_item() to route keystrokes into it.
                # That doesn't work: focus_item() only sets ImGui
                # *navigation* focus, not the *active* edit state a text
                # box needs to actually receive characters (normally only
                # entered via a real mouse click, or SetKeyboardFocusHere()
                # called before the widget draws). is_item_focused() still
                # reports True once nav-focus lands, so the refresh loop's
                # "refocus if not focused" guard silently stopped trying
                # and the box sat there forever, never active, never
                # receiving anything - confirmed by a print() in
                # _on_key_input never firing.
                #
                # Key press handlers sidestep text-widget activation
                # entirely: they fire on the whole viewport, independent
                # of what ImGui considers "focused" or "active". No hidden
                # widget, no refocus-juggling, no click handler needed.
                with dpg.handler_registry():
                    dpg.add_key_press_handler(callback=self._on_key_press)

        dpg.bind_item_theme(self._window_tag, self._theme_tag)

        if self._font_tag is not None:
            dpg.bind_font(self._font_tag)

        dpg.create_viewport(
            title=self.window_title,
            width=self.cols * (self.font_size + 2) + 40,
            height=self.rows * (self.font_size + 4) + 60,
        )
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window(self._window_tag, True)

        if self.capture_keyboard:
            # Route the emulator's keyboard polling through this window
            # instead of msvcrt/the console. Keyboard.poll() in SuperIO.py
            # calls sys_getkey() by name each time it runs, so repointing
            # that name at runtime is enough - no edits needed there or
            # in Emulator.py. Whichever window you're actually typing
            # into (this one) is now the one that matters.
            if SuperIO is not None:
                SuperIO.sys_getkey = self.get_key

    # ---- Keyboard capture --------------------------------------------------
    # dpg.add_key_press_handler's app_data is a DPG key CODE (dpg.mvKey_*).
    # IMPORTANT: these are NOT ASCII codes and NOT Windows VK codes - they're
    # Dear ImGui's internal ImGuiKey enum values (mvKey_A == 546 in this DPG
    # build, not 65). chr(key) on that produces garbage/unrelated unicode
    # characters, which is exactly the scrambled "#/% 5)'..." output we saw:
    # those were leftover low bytes of the wrong codepoint after later &0xFF
    # masking, not an intentional mapping. There is no arithmetic shortcut
    # here - we build an explicit lookup table from the real mvKey_* constants
    # (built once at class-definition time so it's not rebuilt per keystroke)
    # to the characters they represent, and use dpg.is_key_down() for shift
    # state the same way as before.
    #
    # DPG BUG: dpg.mvKey_Colon, mvKey_Quote, mvKey_Plus and mvKey_Tilde are
    # stale leftovers from an older, pre-ImGuiKey-refactor version of the API
    # (values 59/39/61/96 - old raw ASCII-ish codes) that were never updated
    # when the rest of the punctuation keys moved to Dear ImGui's real
    # ImGuiKey enum (Comma=597, Minus=598, Period=599, Slash=600, and so on,
    # all clustered together). The keys they're SUPPOSED to represent do
    # fire real key-press events - just under different numeric codes that
    # DearPyGui 2.3.1 never exposed a matching constant name for:
    #   ' (Apostrophe) = 596   ; (Semicolon) = 601
    #   = (Equal)      = 602   ` (GraveAccent) = 606
    # (confirmed against Dear ImGui's ImGuiKey enum - these sit in the exact
    # gaps between the correctly-exposed constants above/below them). Using
    # the named mvKey_Colon/Quote/Plus/Tilde constants means those four keys
    # never match anything and silently no-op - which is why ';', ':', "'",
    # '"' (and, not yet hit but equally broken: '=', '+', '`', '~') never
    # even reach the interrupt queue. Hardcode the real values below instead
    # of relying on the (wrong) named constants for just these four.
    _APOSTROPHE_KEY = 596
    _SEMICOLON_KEY = 601
    _EQUAL_KEY = 602
    _GRAVE_ACCENT_KEY = 606

    _LETTER_KEYS = {getattr(dpg, f"mvKey_{c}"): c.lower() for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}
    _DIGIT_KEYS = {getattr(dpg, f"mvKey_{d}"): d for d in "0123456789"}
    _PUNCT_KEYS = {
        dpg.mvKey_Minus: ("-", "_"), _EQUAL_KEY: ("=", "+"),
        dpg.mvKey_Open_Brace: ("[", "{"), dpg.mvKey_Close_Brace: ("]", "}"),
        dpg.mvKey_Backslash: ("\\", "|"), _SEMICOLON_KEY: (";", ":"),
        _APOSTROPHE_KEY: ("'", '"'), dpg.mvKey_Comma: (",", "<"),
        dpg.mvKey_Period: (".", ">"), dpg.mvKey_Slash: ("/", "?"),
        _GRAVE_ACCENT_KEY: ("`", "~"),
    }
    _DIGIT_SHIFTED = {
        "0": ")", "1": "!", "2": "@", "3": "#", "4": "$",
        "5": "%", "6": "^", "7": "&", "8": "*", "9": "(",
    }
    _SPECIAL_KEYS = {
        dpg.mvKey_Back: 8, dpg.mvKey_Tab: 9, dpg.mvKey_Return: 13,
        dpg.mvKey_Escape: 27, dpg.mvKey_Spacebar: 32,
    }

    def _on_key_press(self, sender, app_data):
        key = app_data  # a dpg.mvKey_* int (NOT an ASCII code - see note above)

        if key == dpg.mvKey_CapsLock:
            self._caps_lock = not self._caps_lock
            return  # the lock toggle itself isn't a character to send

        if key in self._SPECIAL_KEYS:
            self._key_queue.put(self._SPECIAL_KEYS[key])
            return

        shift = dpg.is_key_down(dpg.mvKey_LShift) or dpg.is_key_down(dpg.mvKey_RShift)

        if key in self._LETTER_KEYS:
            ch = self._LETTER_KEYS[key]
            # Caps Lock and Shift combine by XOR for letters: caps-on +
            # shift-off -> upper, caps-on + shift-on -> lower (shift
            # temporarily cancels the lock), same as a real keyboard.
            # Caps Lock does NOT affect digits/punctuation shifting below.
            ch = ch.upper() if (shift != self._caps_lock) else ch.lower()
        elif key in self._DIGIT_KEYS:
            d = self._DIGIT_KEYS[key]
            ch = self._DIGIT_SHIFTED[d] if shift else d
        elif key in self._PUNCT_KEYS:
            unshifted, shifted = self._PUNCT_KEYS[key]
            ch = shifted if shift else unshifted
        else:
            return  # arrows, F-keys, modifiers, etc. - add to _SPECIAL_KEYS if you need one

        self._key_queue.put(ord(ch))

    def get_key(self):
        """
        Drop-in replacement for SuperIO.sys_getkey(): returns the next
        queued keycode (int), or False if nothing's been typed. Same
        contract as the original msvcrt-based version.
        """
        try:
            return self._key_queue.get_nowait()
        except queue.Empty:
            return False

    # ---- Keep cols/rows in sync with the actual window size ------------
    # Mirrors what os.get_terminal_size() gave the terminal version every
    # frame, just computed from the DPG viewport's pixel size instead.
    # Assumes a monospace bitmap font where each glyph is roughly
    # font_size px wide/tall, which holds for retro 8x8-style fonts.
    def _sync_dimensions_to_viewport(self):
        try:
            vp_w = dpg.get_viewport_client_width()
            vp_h = dpg.get_viewport_client_height()
        except Exception:
            return
        if vp_w <= 0 or vp_h <= 0:
            return
        char_w = max(self.font_size, 1)
        char_h = max(self.font_size + 1, 1)  # +1 roughly matches the tightened row spacing
        self.cols = max(10, vp_w // char_w)
        self.rows = max(5, vp_h // char_h)

    # ---- Feed a raw blob directly (newlines interpreted automatically) -
    def feed_text(self, text: str, color=DEFAULT_COLOR):
        """
        Shortcut for the 'just give it a big gulp of text' use case,
        bypassing the memref/ports walk entirely. \\n splits lines,
        long lines wrap at `self.cols`, exactly like the terminal version.
        """
        self._render_runs([(color, None, text)])

    # ---- Same byte-walk logic as your original, but building runs ------
    def _collect_frame_runs(self):
        if System is None or SuperIO is None:
            raise RuntimeError(
                "Emu.System / Emu.SuperIO could not be imported, so the "
                "memref/ports refresh path can't run. Use feed_text() "
                "instead, or fix the Emu import (check it's on sys.path)."
            )
        System.memory.Map.VIDEO = [
            self.prtref.read(port=SuperIO.PORTs.VIDEO_START_ADDR_PORT),
            self.prtref.read(port=SuperIO.PORTs.VIDEO_END_ADDR_PORT),
        ]

        runs = []
        current_color = DEFAULT_COLOR
        current_bg = None
        current_chars = []

        _pointer = self.prtref.read(port=SuperIO.PORTs.VIDEO_START_ADDR_PORT)
        end = self.prtref.read(port=SuperIO.PORTs.VIDEO_END_ADDR_PORT)

        while _pointer <= end:
            current_byte = self.memref.read_byte(_pointer)
            if current_byte == 0:
                break

            if 10 <= current_byte <= 126:
                current_chars.append(chr(current_byte))
            elif current_byte in COLOR_MAP:
                if current_chars:
                    runs.append((current_color, current_bg, "".join(current_chars)))
                    current_chars = []
                current_color = COLOR_MAP[current_byte]
                if current_byte == RESET_BYTE:
                    current_bg = None  # RESET clears background too, same as a real terminal
            elif current_byte in BG_COLOR_MAP:
                if current_chars:
                    runs.append((current_color, current_bg, "".join(current_chars)))
                    current_chars = []
                current_bg = BG_COLOR_MAP[current_byte]

            _pointer += 1

        if current_chars:
            runs.append((current_color, current_bg, "".join(current_chars)))

        do_cursor = self.prtref.read(SuperIO.PORTs.VIDEO_RENDER_CURSOR_BOOL) == 1
        if do_cursor:
            milliseconds = int((time.monotonic() - self.start_time) * 1000)
            self.cursor_flag = (milliseconds // 500) % 2 == 0
        else:
            self.cursor_flag = False

        if self.cursor_flag:
            runs.append((CURSOR_COLOR, None, self.cursor_glyph))

        return runs

    # ---- Turn runs -> wrapped, padded lines -> DPG widgets --------------
    def _render_runs(self, runs):
        full_text = "".join(text for _, _, text in runs)

        if full_text == self.last_frame:
            return
        self.last_frame = full_text

        lines = full_text.split("\n")
        lines = wrap_to_width(lines, self.cols)

        # Colorize against the FULL wrapped line list first, so the
        # character walk in _runs_per_line always stays aligned with
        # full_text. Truncating/padding to `rows` happens only *after*,
        # on the already-colorized rows - truncating the plain-text lines
        # before colorizing (the old order) desyncs the walk against
        # whatever got cut off the front, scrambling everything past it.
        line_runs = self._runs_per_line(runs, lines)

        if len(line_runs) < self.rows:
            line_runs = line_runs + [[]] * (self.rows - len(line_runs))
        else:
            line_runs = line_runs[-self.rows:]

        dpg.delete_item(self._text_tag, children_only=True)
        for line in line_runs:
            with dpg.group(horizontal=True, parent=self._text_tag):
                if not line:
                    dpg.add_text(" ")
                for fg, bg, chunk in line:
                    if bg is not None:
                        # dpg.add_text has no background fill at all - Dear
                        # ImGui just draws colored glyphs, full stop. A
                        # button is the simplest DPG widget that actually
                        # paints a background rectangle behind its label,
                        # so bg runs get rendered as themed, non-interactive
                        # buttons instead of plain text.
                        item = dpg.add_button(label=chunk, small=True)
                        dpg.bind_item_theme(item, self._get_bg_theme(fg, bg))
                    else:
                        dpg.add_text(chunk, color=fg)

    def _get_bg_theme(self, fg, bg):
        """Lazily build (and cache) a button theme for a given fg/bg pair.

        Built once per (fg, bg) combo and reused across every frame/chunk
        that needs it - creating a fresh dpg.theme() every frame would leak
        theme registry entries forever, since _render_runs wipes the text
        group's children every frame but themes aren't children of it.
        """
        key = (fg, bg)
        if key not in self._bg_theme_cache:
            with dpg.theme() as theme:
                with dpg.theme_component(dpg.mvButton):
                    # Same color for normal/hovered/active so mousing over
                    # or clicking a bg-color run (harmless - no callback is
                    # attached) doesn't flash a different shade.
                    dpg.add_theme_color(dpg.mvThemeCol_Button, bg, category=dpg.mvThemeCat_Core)
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, bg, category=dpg.mvThemeCat_Core)
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, bg, category=dpg.mvThemeCat_Core)
                    dpg.add_theme_color(dpg.mvThemeCol_Text, fg, category=dpg.mvThemeCat_Core)
                    dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0, category=dpg.mvThemeCat_Core)
                    dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 0, category=dpg.mvThemeCat_Core)
            self._bg_theme_cache[key] = theme
        return self._bg_theme_cache[key]

    def _runs_per_line(self, runs, wrapped_lines):
        """Re-associate (fg, bg) colors with the final wrapped/padded line list."""
        flat = []
        for fg, bg, text in runs:
            for ch in text:
                flat.append((fg, bg, ch))

        out = []
        idx = 0
        for line in wrapped_lines:
            line_out = []
            cur_fg = None
            cur_bg = None
            cur_chunk = []
            for _ in line:
                if idx < len(flat):
                    fg, bg, ch = flat[idx]
                    idx += 1
                else:
                    fg, bg, ch = DEFAULT_COLOR, None, " "
                if (fg, bg) != (cur_fg, cur_bg):
                    if cur_chunk:
                        line_out.append((cur_fg, cur_bg, "".join(cur_chunk)))
                    cur_fg, cur_bg = fg, bg
                    cur_chunk = [ch]
                else:
                    cur_chunk.append(ch)
            if cur_chunk:
                line_out.append((cur_fg, cur_bg, "".join(cur_chunk)))
            out.append(line_out)
            if idx < len(flat) and flat[idx][2] == "\n":
                idx += 1
        return out

    # ---- Background thread: owns build() AND the DPG render loop -------
    # This mirrors your call site in Emulator.py exactly:
    #     VMDisplayThread = VMDisplay.spawn_refresh_thread()
    #     VMDisplayThread.start()
    # Nothing else calls build()/run() for you, so this thread has to do
    # everything itself, the same way System.start_gui()'s Tk thread owns
    # its own root and mainloop. can_refresh gates how often we re-walk
    # memory and rebuild the text (~30fps, same cadence as before), but we
    # still pump dpg.render_dearpygui_frame() every loop iteration so the
    # window stays responsive (draggable, resizable, closable) even while
    # can_refresh is False and the emulator hasn't booted yet.
    def spawn_refresh_thread(self):
        def refresh_thread():
            self.build()
            last_poll = 0.0
            while not self.threadExit and dpg.is_dearpygui_running():
                now = time.monotonic()
                if self.can_refresh and (now - last_poll) >= 0.03333:
                    self._sync_dimensions_to_viewport()
                    runs = self._collect_frame_runs()
                    self._render_runs(runs)
                    last_poll = now
                dpg.render_dearpygui_frame()
                time.sleep(0.001)  # yield instead of pegging a core

            if dpg.is_dearpygui_running():
                dpg.stop_dearpygui()
            dpg.destroy_context()

        return threading.Thread(target=refresh_thread, daemon=True)

    # ---- Blocking render loop, for single-threaded/standalone use only -
    def run(self):
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
        dpg.destroy_context()


if __name__ == "__main__":
    # Minimal smoke test that doesn't need the Emu system at all - just
    # proves the GUI + font + text-wrapping side works. This calls
    # build()/run() directly because there's no emulator main-loop
    # competing for the main thread here. In real usage (Emulator.py),
    # spawn_refresh_thread() handles build()+the render loop itself inside
    # its own thread - don't call build()/run() yourself there, just
    # spawn_refresh_thread() + .start(), same as you already do.
    d = GuiDisplay(cols=60, rows=20, font_path=None,  # put a real 8x8 ttf path here
                   window_title="GuiDisplay smoke test")
    d.build()
    d.feed_text(
        "SYSTEM BOOT OK\n"
        "line two with a color switch\n"
        "this line is intentionally long enough that it should wrap onto a second row automatically\n"
        "\n"
        "> _"
    )
    d.run()