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
import signal 
import argparse

DEBUG = True
WINDOWS = os.name == 'nt'

STD_INPUT_HANDLE  = -10
STD_OUTPUT_HANDLE = -11
STD_ERROR_HANDLE  = -12

def debug(msg):
    if DEBUG:
        with open('debug.log', 'a') as fi:
            fi.write(msg + '\n')

def init_debug():
    with open('debug.log', 'w') as fi:
        fi.write('')

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
    if os.name == 'posix':
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
    if os.name == 'posix':
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

def handler(signum, frame):
    print('Signal %s handled.' % signum)
    raise urwid.ExitMainLoop()

class MultiPager():
    
    def __init__(self, files):

        DIV_CHAR = '-'
        self.pagers = []
        widgets = []
        for file_path in files:
            pager = Pager(file_path)
            text_widget = urwid.Text(pager.get_page())
            self.pagers.append((pager, text_widget))
            widgets.append(urwid.Filler(text_widget))
            widgets.append(('pack', urwid.Divider(DIV_CHAR)))
        
        self.window = urwid.Pile(widgets)

    def run(self):
        urwid.MainLoop(self.window, unhandled_input=self.handle_input).run()

    def handle_input(self, key):
        if isinstance(key, str):
            if key.lower() == 'q':
                raise urwid.ExitMainLoop()
            if key == 'up':
                for pager, widget in self.pagers:
                    pager.up()
            if key == 'down':
                for pager, widget in self.pagers:
                    pager.down()
            if key == 'page up':
                for pager, widget in self.pagers:
                    pager.page_up()
            if key == 'page down':
                for pager, widget in self.pagers:
                    pager.page_down()
            if key == 'home':
                for pager, widget in self.pagers:
                    pager.home()
            if key == 'end':
                for pager, widget in self.pagers:
                    pager.end()

        for pager, widget in self.pagers:
            debug("Marker: %s" % pager.marker)
            widget.set_text(pager.get_page())

class Pager():

    def __init__(self, file_handle):

        import codecs
        self.marker = 0
        self.fi = codecs.open(file_handle)
        self.offsets = build_offsets(self.fi)

    def get_page(self):
        """
        """
        lines = []
	height = getheight()
        self.fi.seek(self.offsets[self.marker])
        end = self.marker + height
        current = self.marker
        while current < end:
            line = self.fi.readline()
            # urwid.Text does not handle tabs well
            line = line.replace('\t', '    ')
            lines.append(line)
            current += 1
        return lines

    def up(self):
        if self.marker >  0:
           self.marker -= 1

    def down(self):
        if self.marker < (len(self.offsets) - getheight()):
            self.marker += 1

    def page_up(self):

        # don't try to go up beyond start
        self.marker = max(0, self.marker - getheight())

    def page_down(self):
        # don't try to go down beyond end
        self.marker = min(len(self.offsets) - getheight(), self.marker + getheight())

    def home(self):
        self.marker = 0

    def end(self):
        self.marker = len(self.offsets) - getheight()

def main(files):

    # Exit cleanly on ctrl-c
    signal.signal(signal.SIGINT , handler)
    if DEBUG:
        init_debug()
    # Start the application
    MultiPager(files).run()

if __name__ == '__main__':

    parser = argparse.ArgumentParser('Multi-Log Viewer')
    parser.add_argument('files', nargs='*')
    args = parser.parse_args()

    main(args.files)

