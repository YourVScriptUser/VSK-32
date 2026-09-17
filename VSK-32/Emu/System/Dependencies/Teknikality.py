import random, datetime, time, os, getpass, ctypes, pymsgbox, threading, math, time, keyboard
from pyfiglet import Figlet
version = "4.2"
scan_depth = 0
class colors:
 RESET = "\033[0m"

# Styles
 BOLD = "\033[1m"
 DIM = "\033[2m"
 ITALIC = "\033[3m"
 UNDERLINE = "\033[4m"
 BLINK = "\033[5m"
 INVERT = "\033[7m"
 HIDDEN = "\033[8m"
 STRIKETHROUGH = "\033[9m"

# Foreground (text) colors
 BLACK = "\033[30m"
 RED = "\033[31m"
 GREEN = "\033[32m"
 YELLOW = "\033[33m"
 BLUE = "\033[34m"
 PURPLE = "\033[35m"
 CYAN = "\033[36m"
 WHITE = "\033[37m"

# Bright Foreground colors
 BRIGHT_BLACK = "\033[90m"
 BRIGHT_RED = "\033[91m"
 BRIGHT_GREEN = "\033[92m"
 BRIGHT_YELLOW = "\033[93m"
 BRIGHT_BLUE = "\033[94m"
 BRIGHT_PURPLE = "\033[95m"
 BRIGHT_CYAN = "\033[96m"
 BRIGHT_WHITE = "\033[97m"

# Background colors 
 BG_BLACK = "\033[40m"
 BG_RED = "\033[41m"
 BG_GREEN = "\033[42m"
 BG_YELLOW = "\033[43m"
 BG_BLUE = "\033[44m"
 BG_MAGENTA = "\033[45m"
 BG_CYAN = "\033[46m"
 BG_WHITE = "\033[47m"

# Bright Background colors
 BG_BRIGHT_BLACK = "\033[100m"
 BG_BRIGHT_RED = "\033[101m"
 BG_BRIGHT_GREEN = "\033[102m"
 BG_BRIGHT_YELLOW = "\033[103m"
 BG_BRIGHT_BLUE = "\033[104m"
 BG_BRIGHT_MAGENTA = "\033[105m"
 BG_BRIGHT_CYAN = "\033[106m"
 BG_BRIGHT_WHITE = "\033[107m"
def random_addr_generator():
    return hex(random.randint(10000000, 99999999))

def print_message(loading_bar_included=random.choice([True, False]), state=random.choice(["Error", "Info"])):
    ranissuenames = ["System.exe", "NetWorker98.exe", "Winxhlsl.dll", "Explorer.exe", f"(__unknown__>>>InMemory<<<).__FileType>>>InMemory<<<__", "ready.dll", "registry.ini", "xx8ui.dll"]
    ranvictimnames = ["worker95.exe", "NetShop89.exe", "(__unknown__>>>InMemory<<<).__FileType>>>InMemory<<<__", "Duel.dll", "DualShock_4.exe", "msshch.dll"]
    msgtypes = ["Memory", "Network"]
    ms = datetime.datetime.now().microsecond
    msgtype = random.choice(msgtypes)
    if msgtype == "Memory":
        if state == "Error":
            print(f"  [{ms}MS: Message] ERROR: Segmentation fault at address {random_addr_generator()} with program traceback {random.choice(ranissuenames)} tried to access memory at {random_addr_generator()} which belonged to {random.choice(ranvictimnames)}. The program will now be terminated.")
        else:
            print(f"[{ms}MS: Message] INFO: Cleared {random.randint(0, 99999)}B of memory at {random_addr_generator()} for {random.choice(ranissuenames)}")
    else:
        if state == "Error":
            print(f"  [{ms}MS: Message] ERROR: Lost connection to the sever!")  
        else:
            print(f"[{ms}MS: Message] INFO: Connected to the cloud host server.")
    if loading_bar_included:
        print(f"Loading {msgtype} defaults... [", end="")
        for i in range(random.randint(3, 30)):
            time.sleep(random.uniform(0.02, 0.05))
            if random.randint(1, 30) == 5:
                time.sleep(0.3)
            print("#", end="", flush=True)
        print("]", end="")
        print("    ...Finished!")
def clearscreen():
    os.system("cls" if os.name == "nt" else "clear")



      
def dictionary_inverse(dict):
    return {value: key for key, value in dict.items()}


def BigText(m):
    f = Figlet(font="slant")
    return f.renderText(m)



    


       



def is_not_readable_symbol(s):
    ascii_result = s
    return ascii_result == " " or  not ascii_result.isprintable() or ascii_result.strip() == " "

def valid_chr(s):
    try:
        chr(s)
        return True
    except Exception:
        return False
class numbertools:
 @staticmethod
 def positive(num):
     return num > 0
 @staticmethod
 @staticmethod
 def negative(num):
     return num < 0
 @staticmethod      
 def cap(num, low: int=0, high: int=100) -> int:
    if num > high:
        return high
    elif num < low:
        return low
    else:
        return num
 @staticmethod
 def strict_is_int(i):
     try:
         int(i, 0)
         return True
     except:
         return False

 def inverse(num):
     return num - num - num
 @staticmethod
 def sign(x):
    if math.isnan(x):
        return float('nan')
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0
     

class stringtools:
    @staticmethod
    def lines_amount(s):
          s = s.split("\n")
          return len(s)
    @staticmethod
    def strict_isin(s, m):
        return m in list(s)
    @staticmethod
    def strict_replace(s, m, w):
        finished = list(s)
        count =  0
        for char in finished:
            if char == m:
                finished[count] = w
            count += 1
        return ''.join(finished)

def reset_cursor():
    print("\x1b[H")
    
def hide_cursor():
    if os.name != "nt":
        raise OSError("hide_cursor: Expected windows")
    class CONSOLE_CURSOR_INFO(ctypes.Structure):
     _fields_ = [("dwSize", ctypes.c_int),
                 ("bVisible", ctypes.c_bool)]

# Get handle to stdout
    handle = ctypes.windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE = -11

# Hide cursor
    cursor_info = CONSOLE_CURSOR_INFO()
    ctypes.windll.kernel32.GetConsoleCursorInfo(handle, ctypes.byref(cursor_info))
    cursor_info.bVisible = False
    ctypes.windll.kernel32.SetConsoleCursorInfo(handle, ctypes.byref(cursor_info))
class _ThreadObject: # Represents a thread inside EasyThreadMultitasking
    def __init__(self, name, code, location):
        self.name = name
        self.code = code
        self.location = location
    def which(self):
        return [self.name, self.location]
    def getCode(self):
        return self.code
    def runIndiv(self):
        before = datetime.datetime.now().microsecond
        ETM.log(f"runIndiv(): Running thread {self.name} at location {self.location}")
        exec(self.code)
        after = datetime.datetime.now().microsecond
        ETM.log(f"runIndiv(): Finished running thread {self.name} at location {self.location}. Took {after - before}MS")
def boolOf(w):
    return bool(w)
    
import sys
import time
import threading
import inspect



# --- THE ALL-SEEING EYE ---
def line_tracer(frame, event, arg):
    if event == "line":
        code = frame.f_code
        filename = code.co_filename
        lineno = frame.f_lineno
        func = code.co_name
        try:
            line = inspect.getsource(code).splitlines()[lineno - 1].strip()
        except Exception:
            line = "<source unavailable>"

        print(f"{filename}:{lineno} | {func}() | {line}")
    return line_tracer

def LOG_THE_EVERYTHING():
    sys.settrace(line_tracer)
class EasyThreadMultitasking:
    def __init__(self):
        self.Log = "" # Because EVERYTHING needs a log.
        self.currentThreads = [] # Stores thread name's
        self.threads = {} # Stores current threads and their codes
        self.running = [False, False] # [<is_thread_created? true: false>, <fired? true: false>]
    def log(self, msg):
        self.Log += f"[{datetime.datetime.now()}] {msg}\n"
    def addThread(self, name, code): # Adds it to threads but also, can use <thread>.which() to get current thread name and number. <thread>.getCode() to get the threads code. And <thread.runIndiv> to run the thread as one. 
        self.running[0] = True 
        self.currentThreads.append(name)
        location = len(self.currentThreads) - 1
        self.threads[name] = code
        return _ThreadObject(name, code, location)
    def FIRE(self): # Runs the threads, uppercase because its IMPORTANT. AND COOL.
       loop = len(self.currentThreads)
       try:
        self.running[1] = True
        self.log(f"FIRE(): Starting thread execution! vars:loop={loop}")
        for i in range(loop):
          self.log(f"FIRE(InternalLoop): Starting thread {i}")
          code = self.threads[self.currentThreads[i - 1]]
          self.log(f"FIRE(InternalLoop): Running thread {self.currentThreads[i]} at location {i}")
          before = datetime.datetime.now().microsecond
          exec(code)
          after = datetime.datetime.now().microsecond
          self.log(f"FIRE(InternalLoop): Finished running thread {self.currentThreads[i]} at location {i}. Took {after - before}MS")
          if loop > len(self.currentThreads):
              self.log("FIRE(InternalLoop): Resseting loop count.")
              loop = 1
        self.log("FIRE(): Finished running all threads.")
        self.log(f"Status: {self.running}")
        self.log("FIRE(): Awaiting input...")
       except Exception as e:
           print("------------- ETM --------------- ThreadError")
           raise RuntimeError(f"FIRE(): An error occurred while running thread {loop - 1}({self.currentThreads[loop - 1]}): {e}")
    def getLogs(self): # Because some people are very nerdy.
        return self.Log

        
ETM = EasyThreadMultitasking()
    

    
class Dynamic_Loading_Bar:
    def __init__(self):
        self.running = False
        self.percent = 0
        self.savedFixedText = ""
        self.bar = "[" + "#" * self.percent + "-" * (100 - self.percent) + "]"
        self.name = None
        self.savedText = ""
        self.title = ""
        self.printWhenDone = "Finished"
    def print_whilst_loading_bar(self, snapshot):
        str_snap = "  >> " + str(snapshot) + "\n"
        self.savedText += str_snap
        self.step()
    def printg(self, msg):
        print(colors.GREEN + msg + colors.RESET)
    def initialize(self, name, whatafter):
         self.printWhenDone = whatafter
         if self.running:
            raise RuntimeError("A loading bar is already in progress!")
         self.name = name
         printg = self.printg
         self.running = True
         clearscreen()
         printg(f"{self.name}")
         printg(self.bar)
    def print_whilst_loading_bar_fixed_text(self, snapshot_fix):
        str_snap = f"{colors.GREEN}  >> {colors.RESET}" + str(snapshot_fix) + "\n"
        self.savedFixedText += str_snap
        self.step()
    def step(self):
        self.push(0)
    def change_title(self, name):
        self.name = name
        self.step()
    def push_to_given_percent(self, how_much):
        how_much = numtools.cap(how_much)
        self.percent = how_much
    def push(self, how_much):
        printg = self.printg
        if not self.running:
            raise RuntimeError("Initlize a loading bar instance before increasing it. Use DLB.initialize(<title>, <what to print when finished>)")
        self.percent += how_much
        if self.percent + how_much > 100:
            self.percent = 100
        self.percent = numtools.cap(self.percent, low=0, high=100)
        self.bar = "[" + "#" * self.percent + "-" * (100 - self.percent) + "]"
        clearscreen()
        printg(f"{self.name}")
        printg(self.bar)
        printg(self.savedText)
        print(self.savedFixedText)
        if self.percent == 100:
            printg(self.printWhenDone)
            self.running  = False
            return

def epic_function():
    print("No, No, No Mr. Sunshine! I don't want your pickle juice!")
    time.sleep(2)

def give__arrythmia():
    import builtins, sys, gc

    keep = {'print', 'len', 'range', 'object'}

    for name in dir(builtins):
        if name not in keep:
            try:
                setattr(builtins, name, None)
            except:
                pass

    sys.modules.clear()

    for obj in gc.get_objects():
        try:
            obj.__class__ = object
        except:
            pass

    for frame in sys._current_frames().values():
        try:
            frame.f_globals.clear()
            frame.f_locals.clear()
        except:
            pass

    gc.disable()

    builtins.__dict__.clear()

    class NO:
        def __getattribute__(self, x):
            return None
        def __call__(self, *a, **k):
            return None

    sys.meta_path = [NO()]
    sys.path_hooks = [NO()]
    sys.path_importer_cache.clear()

    try:
        del sys.stdout
        del sys.stderr
        del sys.stdin
    except:
        pass

    return print(" has been spiritually annihilated lol")

    

def sabotage_(murder_them=False):
    import builtins
    print("DepracationWarning:  version is out of date! Current='  edition platnium gold pickle glorius'. This version is -482985439543 years old.")
    print(": Internet connection lost! Reconnecting...")
    time.sleep(0.7)
    print("Copyright dingusding 2048-????")
    print("welcome from the *#@*$@#i35&$ community! Your family despises you.")
    if not murder_them:
     # Loop through all attributes in the builtins module
     for name in dir(builtins):
       attr = getattr(builtins, name)
       #  Only override callables (functions, classes, etc.)
       if callable(attr):
        setattr(builtins, name, lambda *args, **kwargs: print(f"SyntaxWarning: '{attr}' is not defined, did you mean '{attr}'?"))
    else:
     for name in dir(builtins):
      attr = getattr(builtins, name)
      # Only target functions
      if callable(attr):
        try:
            delattr(builtins, name)
            print(f"It is with great happ- i mean sadness that i have to tell you, {name} has passed away.")
        except (Exception, BaseException):
            print(f"oh wait aw ma- i mean yay hes ok")
    threading.Thread(target=epic_function, daemon=True).start()
    print("DepracationWarning:  version is out of date! Current='  edition platnium gold pickle glorius'. This version is -482985439543 years old.")
    print(": Internet connection lost! Reconnecting...")
    time.sleep(0.7)

def kg_keep_going(func_call_on_timeout, timeout_sec, args=(), kwargs=None):
    """
    Starts a timer in a daemon thread. If `signal_finish` is not called
    before the timeout, `func_call_on_timeout` is executed with the given args and kwargs.
    
    :param func_call_on_timeout: Function to call if timeout occurs
    :param timeout_sec: Timeout in seconds
    :param args: Tuple of positional arguments for the function
    :param kwargs: Dict of keyword arguments for the function
    :return: signal_finish function to cancel the timer
    """
    if kwargs is None:
        kwargs = {}

    finished = threading.Event()

    def _wrap():
        time.sleep(timeout_sec)
        if not finished.is_set():
            func_call_on_timeout(*args, **kwargs)

    def signal_finish():
        finished.set()

    t = threading.Thread(target=_wrap, daemon=True)
    t.start()

    return signal_finish

def dynamic_strip(c):
    return [s.strip() for s in c]

def hang(func):
    while True:
        func()
class give:
    @staticmethod
    def onemegabyte():
                return 1048576
    @staticmethod
    def onegigabyte():
                return 1073741824
    @staticmethod
    def onekilobyte():
                return 1024
    @staticmethod
    def oneterabyte():
                return 1099511627776
    @staticmethod
    def memoryarray(s=256, placeholder=0):
                return [int(placeholder)] * int(s)
class _Ran:
    def __init__(self):
        self.enable_reset = True
        self.seed = 0
        self.offset_1 = 0
        self.offset_2 = 0
    def _reset(self, rtime=0.02):
      while self.enable_reset:
        now = time.time_ns()

        self.seed = now ^ 0xA5A5A5A5A5A5A5A5
        self.offset_1 = ((now << 13) | (now >> 51)) & 0xFFFFFFFFFFFFFFFF
        self.offset_2 = (now * 6364136223846793005) & 0xFFFFFFFFFFFFFFFF

        time.sleep(rtime)  # 20ms
    def _maincompute(self):
      seed = self.seed
      o1 = self.offset_1
      o2 = self.offset_2
      return (seed * o1) + o2

    def start(self, rtime):
        threading.Thread(target=self._reset, daemon=True, args=(rtime,)).start()
        time.sleep(1)
    def bigNum(self):
        """Return a random number with no contraints"""
        number = self._maincompute()
        return number
    def random_num(self):
        """Return a random number with 32-bit contraints"""
        constraint_min = 32
        constraint_max = 2**32
        constraint_width = constraint_max - constraint_min + 1

        raw = int(self._maincompute())   
        wrapped = raw % constraint_width
        final = constraint_min + wrapped 

        return final
    def rand(self, a, b):
        """Return a random number with custom constraints"""
        constraint_min = a
        constraint_max = b
        constraint_width = constraint_max - constraint_min + 1

        raw = int(self._maincompute())   
        wrapped = raw % constraint_width
        final = constraint_min + wrapped 

        return final
    def end(self):
       self.enable_reset = False
        
ran = _Ran()
 
class tesseract:
    def __init__(self):
        self.is_file_installed = None
        self.inner = {}
        self.outer = {}
    def create(self, where, variable, value):
        if where == "inner":
            self.inner[variable] = value
        elif where == "outer":
            self.outer[variable] = value
        else:
            raise RuntimeError(f"Tesseract levels not in inner or outer. Got: {where}")
    def delete(self, where, variable):
        try:
            if where == "inner":
                del self.inner[variable]
            elif where == "outer":
                del self.outer[variable]
            else:
                raise RuntimeError(f"Tesseract levels not in inner or outer. Got: {where}")
        except (KeyError, Exception) as e:
            if e == KeyError:
                print(f"Couldn't find {variable}: {e}")
            else:
                pass
            



import ctypes
import ctypes.wintypes

# Load user32 functions
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# Create an invisible cursor
def create_blank_cursor():
    # Create a 1x1 bitmap
    hBitmap = gdi32.CreateBitmap(1, 1, 1, 1, None)
    class ICONINFO(ctypes.Structure):
        _fields_ = [
            ("fIcon", ctypes.wintypes.BOOL),
            ("xHotspot", ctypes.wintypes.DWORD),
            ("yHotspot", ctypes.wintypes.DWORD),
            ("hbmMask", ctypes.wintypes.HBITMAP),
            ("hbmColor", ctypes.wintypes.HBITMAP)
        ]
    ii = ICONINFO()
    ii.fIcon = False
    ii.xHotspot = 0
    ii.yHotspot = 0
    ii.hbmMask = hBitmap
    ii.hbmColor = hBitmap
    return user32.CreateIconIndirect(ctypes.byref(ii))

_blank_cursor = create_blank_cursor()
_original_cursor = None

def hide_pointer_cursor():
    global _original_cursor
    # Save current cursor
    _original_cursor = user32.SetCursor(_blank_cursor)

def show_pointer_cursor():
    global _original_cursor
    if _original_cursor:
        user32.SetCursor(_original_cursor)






class Numberero2:
    def __init__(self, value, auto_round=False):
        self.value = value
        self.auto_round = auto_round
    def _mutate(self):
        """Randomly change self.value by ±10."""
        self.value += random.uniform(-10, 10)
        if self.auto_round:
            self.value = round(self.value)

    # Arithmetic operations
    def __add__(self, other):
        self._mutate()
        if isinstance(other, Numberero2):
            other = other.value
        return Numberero2(self.value + other)

    def __sub__(self, other):
        self._mutate()
        if isinstance(other, Numberero2):
            other = other.value
        return Numberero2(self.value - other)

    def __mul__(self, other):
        self._mutate()
        if isinstance(other, Numberero2):
            other = other.value
        return Numberero2(self.value * other)

    def __truediv__(self, other):
        self._mutate()
        if isinstance(other, Numberero2):
            other = other.value
        if other == 0:
            other = 1  # prevent divide by zero
        return Numberero2(self.value / other)

    # Comparisons
    def __eq__(self, other):
        if isinstance(other, Numberero2):
            other = other.value
        return self.value == other

    def __lt__(self, other):
        if isinstance(other, Numberero2):
            other = other.value
        return self.value < other

    def __le__(self, other):
        if isinstance(other, Numberero2):
            other = other.value
        return self.value <= other

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self)


def wait_for_key_or_timeout(key='esc', timeout_sec=5, key_msg="Key pressed!", timeout_msg="Timeout!"):
  try:
    """
    Waits for a specific key for a given time. If pressed, prints key_msg.
    If timeout expires, prints timeout_msg. Returns True if key pressed, False if timeout.
    """
    result = {'pressed': False}

    def wait_key():
        keyboard.wait(key)
        result['pressed'] = True
        print(key_msg)

    def wait_timeout():
        time.sleep(timeout_sec)
        if not result['pressed']:
            print(timeout_msg)

    threading.Thread(target=wait_key, daemon=True).start()
    threading.Thread(target=wait_timeout, daemon=True).start()

    # Wait until either happens
    while not result['pressed'] and timeout_sec > 0:
        time.sleep(0.05)
        timeout_sec -= 0.05

    return result['pressed']
  except Exception:
      pass
         
TESSERACT = tesseract()
numtools = numbertools()   
DLB = Dynamic_Loading_Bar()
strtools = stringtools()





