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
import urwid

DEBUG = False
WINDOWS = os.name == 'nt'

STD_INPUT_HANDLE  = -10
STD_OUTPUT_HANDLE = -11
STD_ERROR_HANDLE  = -12

def debug(msg):
    if DEBUG:
        print(msg)

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



def build_offsets(fi):
    offsets = []
    offset = 0
    original = fi.tell()
    for line in fi:
        offsets.append(offset)
        offset += len(line)
    fi.seek(original)
    return offsets 

focus_map = {
    'heading': 'focus heading',
    'options': 'focus options',
    'line': 'focus line'}

class HorizontalBoxes(urwid.Columns):
    def __init__(self):
        super(HorizontalBoxes, self).__init__([], dividechars=1)

    def open_box(self, box):
        if self.contents:
            del self.contents[self.focus_position + 1:]
        self.contents.append((urwid.AttrMap(box, 'options', focus_map),
            self.options('given', 24)))
        self.focus_position = len(self.contents) - 1

class Pager():

    def __init__(self, fi):
        self.fi = fi
        self.marker = 0
        self.offsets = build_offsets(fi)
        self.txt = urwid.Text(self.get_page(self.fi, self.offsets, self.marker))
        self.fill = urwid.Filler(self.txt, 'top')

    def handle_input(self, key):
        if isinstance(key, str):
            if key.lower() == 'q':
                raise urwid.ExitMainLoop()
            if key == 'up' and self.marker >  0:
                self.marker -= 1
            if key == 'down' and self.marker < (len(self.offsets) - getheight()):
                self.marker += 1
            if key == 'page up':
                # don't try to go up beyond start
                self.marker = max(0, self.marker - getheight())
            if key == 'page down':
                # don't try to go down beyond end
                self.marker = min(len(self.offsets) - getheight(), self.marker + getheight())
            if key == 'home':
                self.marker = 0
            if key == 'end':
                self.marker = len(self.offsets) - getheight()
            
        self.txt.set_text(self.get_page(self.fi, self.offsets, self.marker))

    def get_page(self, fi, offsets, marker):

        """
        """
        debug('-------- MARKER %s -----------' % marker)
        
        lines = []
	height = getheight()
        fi.seek(offsets[marker])
        end = marker + height
        while marker < (end):
            line = fi.readline() #.rstrip("\n\r")
            if not DEBUG:
                lines.append(line)
            marker += 1
        debug("Printed %s lines" % marker)
        return lines

    def run(self):
        loop = urwid.MainLoop(self.fill, unhandled_input=self.handle_input)
        loop.run()


def main(fi):
    pager = Pager(fi)
    pager.run()


if __name__ == '__main__':
    # check if pager.py is running in interactive mode
    # (without stdin redirection)
    with open(sys.argv[1]) as fi:
        main(fi)

    # [ ] check piped stdin in Linux
    #main(cStringIO.StringIO(sys.stdin))

# [ ] add 'q', Ctrl-C and ESC handling to default pager prompt
#     (as of 3.1 Windows aborts only on Ctrl-Break)

