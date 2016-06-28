#!/usr/bin/env python

from __future__ import print_function

"""
Page output and find dimensions of console.

This module deals with paging on Linux terminals and Windows consoles in
a cross-platform way. The major difference for paging here is line ends.
Not line end characters, but the console behavior when the last character
on a line is printed.  To get technical details, run this module without
parameters::

  python pager.py

Author:  anatoly techtonik <techtonik@gmail.com>
License: Public Domain (use MIT if the former doesn't work for you)
"""

# [ ] measure performance of keypresses in console (Linux, Windows, ...)
# [ ] define CAPS LOCK strategy (lowercase) and keyboard layout issues

__version__ = '3.3'

import os
import sys
import cStringIO
import sys, tty, termios


WINDOWS = os.name == 'nt'
PY3K = sys.version_info >= (3,)

# Windows constants
# http://msdn.microsoft.com/en-us/library/ms683231%28v=VS.85%29.aspx

STD_INPUT_HANDLE  = -10
STD_OUTPUT_HANDLE = -11
STD_ERROR_HANDLE  = -12

DEBUG = False

# --- console/window operations ---

if WINDOWS:
    # get console handle
    from ctypes import windll, Structure, byref
    try:
        from ctypes.wintypes import SHORT, WORD, DWORD
    # workaround for missing types in Python 2.5
    except ImportError:
        from ctypes import (
            c_short as SHORT, c_ushort as WORD, c_ulong as DWORD)
    console_handle = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

    # CONSOLE_SCREEN_BUFFER_INFO Structure
    class COORD(Structure):
        _fields_ = [("X", SHORT), ("Y", SHORT)]

    class SMALL_RECT(Structure):
        _fields_ = [("Left", SHORT), ("Top", SHORT),
                    ("Right", SHORT), ("Bottom", SHORT)]

    class CONSOLE_SCREEN_BUFFER_INFO(Structure):
        _fields_ = [("dwSize", COORD),
                    ("dwCursorPosition", COORD),
                    ("wAttributes", WORD),
                    ("srWindow", SMALL_RECT),
                    ("dwMaximumWindowSize", DWORD)]


def _windows_get_window_size():
    """Return (width, height) of available window area on Windows.
       (0, 0) if no console is allocated.
    """
    sbi = CONSOLE_SCREEN_BUFFER_INFO()
    ret = windll.kernel32.GetConsoleScreenBufferInfo(console_handle, byref(sbi))
    if ret == 0:
        return (0, 0)
    return (sbi.srWindow.Right - sbi.srWindow.Left + 1,
            sbi.srWindow.Bottom - sbi.srWindow.Top + 1)

def _posix_get_window_size():
    """Return (width, height) of console terminal on POSIX system.
       (0, 0) on IOError, i.e. when no console is allocated.
    """
    # see README.txt for reference information
    # http://www.kernel.org/doc/man-pages/online/pages/man4/tty_ioctl.4.html

    from fcntl import ioctl
    from termios import TIOCGWINSZ
    from array import array

    """
    struct winsize {
        unsigned short ws_row;
        unsigned short ws_col;
        unsigned short ws_xpixel;   /* unused */
        unsigned short ws_ypixel;   /* unused */
    };
    """
    winsize = array("H", [0] * 4)
    try:
        ioctl(sys.stdout.fileno(), TIOCGWINSZ, winsize)
    except IOError:
        # for example IOError: [Errno 25] Inappropriate ioctl for device
        # when output is redirected
        # [ ] TODO: check fd with os.isatty
        pass
    return (winsize[1], winsize[0])

def getwidth():
    """
    Return width of available window in characters.  If detection fails,
    return value of standard width 80.  Coordinate of the last character
    on a line is -1 from returned value. 

    Windows part uses console API through ctypes module.
    *nix part uses termios ioctl TIOCGWINSZ call.
    """
    width = None
    if WINDOWS:
        return _windows_get_window_size()[0]
    elif os.name == 'posix':
        return _posix_get_window_size()[0]
    else:
        # 'mac', 'os2', 'ce', 'java', 'riscos' need implementations
        pass

    return width or 80

def getheight():
    """
    Return available window height in characters or 25 if detection fails.
    Coordinate of the last line is -1 from returned value. 

    Windows part uses console API through ctypes module.
    *nix part uses termios ioctl TIOCGWINSZ call.
    """
    height = None
    if WINDOWS:
        return _windows_get_window_size()[1]
    elif os.name == 'posix':
        return _posix_get_window_size()[1] - 1
    else:
        # 'mac', 'os2', 'ce', 'java', 'riscos' need implementations
        pass

    return height or 25


# --- keyboard input operations and constants ---
# constants for getch() (these end with _)

if WINDOWS:
    ENTER_ = '\x0d'
    CTRL_C_ = '\x03'
else:
    ENTER_ = '\n'
    # [ ] check CTRL_C_ on Linux
    CTRL_C_ = None
ESC_ = '\x1b'

# other constants with getchars()
if WINDOWS:
    LEFT =  ['\xe0', 'K']
    UP =    ['\xe0', 'H']
    RIGHT = ['\xe0', 'M']
    DOWN =  ['\xe0', 'P']
else:
    LEFT =  ['\x1b', '[', 'D']
    UP =    ['\x1b', '[', 'A']
    RIGHT = ['\x1b', '[', 'C']
    DOWN =  ['\x1b', '[', 'B']
ENTER = [ENTER_]
ESC  = [ESC_]

def dumpkey(key):
    """
    Helper to convert result of `getch` (string) or `getchars` (list)
    to hex string.
    """
    def hex3fy(key):
        """Helper to convert string into hex string (Python 3 compatible)"""
        from binascii import hexlify
        # Python 3 strings are no longer binary, encode them for hexlify()
        if PY3K:
           key = key.encode('utf-8')
        keyhex = hexlify(key).upper()
        if PY3K:
           keyhex = keyhex.decode('utf-8')
        return keyhex
    if type(key) == str:
        return hex3fy(key)
    else:
        return ' '.join( [hex3fy(s) for s in key] )


if WINDOWS:
    if PY3K:
        from msvcrt import kbhit, getwch as __getchw
    else:
        from msvcrt import kbhit, getch as __getchw

def debug(msg):
    if DEBUG:
        print(msg)

def _getch_windows(_getall=False):
    chars = [__getchw()]  # wait for the keypress
    if _getall:           # read everything, return list
        while kbhit():
            chars.append(__getchw())
        return chars
    else:
        return chars[0]


def _getch_unix(_getall=False):
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setraw(sys.stdin.fileno())
    try:
        if _getall:
            ch = sys.stdin.read(1)
            if ch == UP[0]:
                ch = [ch,  sys.stdin.read(1),  sys.stdin.read(1)]
            debug('got %s' % (ch))
        else:
            ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

# choose correct getch function at module import time
if WINDOWS:
    getch = _getch_windows
else:
    getch = _getch_unix

getch.__doc__ = \
    """
    Wait for keypress, return first char generated as a result.

    Arrows and special keys generate sequence of chars. Use `getchars`
    function to receive all chars generated or present in buffer.
    """

    # check that Ctrl-C and Ctrl-Break break this function
    #
    # Ctrl-C       [n] Windows  [y] Linux  [ ] OSX
    # Ctrl-Break   [y] Windows  [n] Linux  [ ] OSX


# [ ] check if getchars returns chars already present in buffer
#     before the call to this function
def getchars():
    """
    Wait for keypress. Return list of chars generated as a result.
    More than one char in result list is returned when arrows and
    special keys are pressed. Returned sequences differ between
    platforms, so use constants defined in this module to guess
    correct keys.
    """
    return getch(_getall=True)
    

def echo(msg):
    """
    Print msg to the screen without linefeed and flush the output.
    
    Standard print() function doesn't flush, see:
    https://groups.google.com/forum/#!topic/python-ideas/8vLtBO4rzBU
    """
    sys.stdout.write(msg)
    sys.stdout.flush()


def build_offsets(fi):
  offsets = []
  offset = 0
  original = fi.tell()
  for line in fi:
      offsets.append(offset)
      offset += len(line)
  fi.seek(original)
  return offsets 

def main(fi):

    marker = 0
    offsets = build_offsets(fi)
    while True:
       page(fi, offsets, marker)
       char = getchars()
       if (char == UP and marker > 0):
           #print("UP")
           marker -= 1
       if (char == DOWN and marker < getheight()):
           #print("DOWN")
           marker += 1 
       if (char == 'q'):
           sys.exit()

def page(fi, offsets, marker=0):
    """
    """
    width = getwidth()
    height = getheight()

    debug('-------- MARKER %s -----------' % marker)

    debug("starting @ %s" % marker)
    fi.seek(offsets[marker])
    end = marker + height
    while marker < (end):
        line = fi.readline() #.rstrip("\n\r")
        if not DEBUG:
            print(line, end='')
            sys.stdout.flush()
        marker += 1
    debug("Printed %s lines" % marker)
    return

if __name__ == '__main__':
    # check if pager.py is running in interactive mode
    # (without stdin redirection)
    with open(sys.argv[1]) as fi:
        main(fi)

    # [ ] check piped stdin in Linux
    #main(cStringIO.StringIO(sys.stdin))

# [ ] add 'q', Ctrl-C and ESC handling to default pager prompt
#     (as of 3.1 Windows aborts only on Ctrl-Break)

