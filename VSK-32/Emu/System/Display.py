# The main refreshing display

from Emu.System import System  
from Emu.System import SuperIO

class Display:
  def __init__(self, mem: System.memory, ports: SuperIO.portio):
     self.memref = mem
     self.prtref = ports
     self.can_refresh = False
     self.last_frame  = ""
     self.threadExit  = False
     self.start_time  = System.time.monotonic() # For cursor time tracing
     self.cursor_flag = False                   # Flag for knowing when the cursor is on or off
  
  def spawn_refresh_thread(self):
    def refresh_thread():
      while not self.threadExit:
        SCREEN_ROWS = System.os.get_terminal_size().lines
        System.memory.Map.VIDEO = [self.prtref.read(port=SuperIO.PORTs.VIDEO_START_ADDR_PORT), self.prtref.read(port=SuperIO.PORTs.VIDEO_END_ADDR_PORT)]
        if self.can_refresh:
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
            _pointer = self.prtref.read(port=SuperIO.PORTs.VIDEO_START_ADDR_PORT)
            while True:
                if _pointer > self.prtref.read(port=SuperIO.PORTs.VIDEO_END_ADDR_PORT):
                    break
  
                current_byte = self.memref.read_byte(_pointer)
                if current_byte == 0:
                    break
  
                if 10 <= current_byte <= 126:
                    Fbuf.append(chr(current_byte))
                elif current_byte in color_map:
                    Fbuf.append(color_map[current_byte])
  
                _pointer += 1
  
            # Append the cursor if the flag is set
            do_cursor = self.prtref.read(SuperIO.PORTs.VIDEO_RENDER_CURSOR_BOOL) == 1
            if do_cursor:
                milliseconds = int((System.time.monotonic() - self.start_time) * 1000)
                self.cursor_flag = (milliseconds // 500) % 2 == 0
            else:
                self.cursor_flag = False
                  
            if self.cursor_flag:
                Fbuf.append("▂")
  
            frame_str = "".join(Fbuf)
  
            if frame_str == self.last_frame:
                System.time.sleep(0.03333)
                continue
  
            size = System.os.get_terminal_size()
            SCREEN_ROWS = size.lines
            SCREEN_COLS = size.columns
            
            lines = frame_str.split("\n")
            lines = wrap_to_width(lines, SCREEN_COLS)  # FIX: Console embedded wraparound was causing newline calculation issues
            
            if len(lines) < SCREEN_ROWS:
                lines += [""] * (SCREEN_ROWS - len(lines))
            else:
                lines = lines[-SCREEN_ROWS:]
  
            out = "\033[H" + "\033[K\r\n".join(lines) + "\033[K"
  
            System.sys.stdout.write(System.Teknikality.colors.RESET + out)
            System.sys.stdout.flush()
  
            System.time.sleep(0.03333)
        else:
            System.time.sleep(0.3)
  
    return System.threading.Thread(target=refresh_thread, daemon=True)

def wrap_to_width(lines, width):
    wrapped = []
    for line in lines:
        if line == "":
            wrapped.append("")
        else:
            for i in range(0, len(line), width):
                wrapped.append(line[i:i+width])
    return wrapped