#!/usr/bin/env python

"""
Page multiple files in the same terminal.

"""

__version__ = '0.2'

import os
import sys
import urwid
import signal 
import argparse

DEBUG = True
WINDOWS = os.name == 'nt'

def debug(msg):
    if DEBUG:
        with open('debug.log', 'a') as fi:
            fi.write(msg.rstrip() + '\n')

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

def handler(signum, frame):
    print('Signal %s handled.' % signum)
    raise urwid.ExitMainLoop()

class MultiPager():
    
    def __init__(self, files):

        DIV_CHAR = '_'
        self.pagers = []
        widgets = []
        rows = getheight() / len(files)
        for file_path in files:
            pager = Pager(file_path, rows)
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
            if key == '/':
                searchBox = (SearchBox(), ('pack', None))
                self.window.contents.append(searchBox)
                self.window.focus_position = len(self.window.contents) - 1
            if key == 'tab':
                self.window.focus_position = (self.window.focus_position + 1) % len(self.window.contents)

        for pager, widget in self.pagers:
            widget.set_text(pager.get_page())

class SearchBox(urwid.Edit):

    def __init__(self, callback):
        super(SearchBox, self).__init__()

    def keypress(self, size, key):
        if key == 'enter':
            text, _ = self.get_text()
            debug("SEARCH: %s" % text)
        super(SearchBox, self).keypress(size, key)


class Pager():

    def __init__(self, file_path, rows):

        self.marker = 0
        self.rows = rows
        self.file_path = file_path
        self.fi = open(file_path)
        self.last_page = self.find_end()

    def get_rows(self):
        return self.rows

    def get_page(self):
        """
        """
        if DEBUG:
            debug('------- PAGE (%s) --------' % self.marker)
        lines = []
	height = self.get_rows()
        self.fi.seek(self.marker)
        current = 0
        while current < height:
            line = self.fi.readline()
            current += 1
            # urwid.Text cannot handle tabs
            line = line.replace('\t', '    ')
            lines.append(line)
            if DEBUG:
                debug(line)
        self.fi.seek(self.marker)
        return lines

    def find_end(self):
        """ calculate the last valid file offset such that we can 
            still display a full page.
        """
        original = self.marker
        self.fi.seek(self.size())
        self.marker = self.fi.tell()
        for i in range(self.get_rows()):
            self.up()
        end = self.marker
        self.marker = original
        debug("End for %s: %s" % (self.file_path, end))
        return end

    def size(self):
        return os.path.getsize(self.file_path)

    def up(self):
        previous_line = reverse_readline(self.fi, self.marker)
        self.marker -= len(previous_line) + 1
        self.marker = max(0, self.marker)

    def down(self):
        next_line = self.fi.readline()
        self.marker += len(next_line)
        self.marker = min(self.last_page, self.marker)

    def page_up(self):
        for i in range(self.get_rows()):
            self.up()

    def page_down(self):
        for i in range(self.get_rows()):
            self.down()

    def home(self):
        self.marker = 0

    def end(self):
        self.marker = self.size()
        self.page_up()

def reverse_readline(fh, start_pos, buf_size=8192):
    """returns the previous line of the file"""
    fh.seek(start_pos)
    remaining_size = fh.tell()
    chunk_size = min(remaining_size, buf_size)
    fh.seek(remaining_size - chunk_size)
    buff = fh.read(chunk_size)
    lines = buff.split('\n')
    if not lines:
        return ''
    else:
        return lines[-1]

def main(files):

    if DEBUG:
        init_debug()
    # Exit cleanly on ctrl-c
    signal.signal(signal.SIGINT , handler)
    # Start the application
    MultiPager(files).run()

if __name__ == '__main__':

    parser = argparse.ArgumentParser('Multi-Log Viewer')
    parser.add_argument('file', nargs='*', help='file path(s)')
    args = parser.parse_args()

    if not args.file:
        parser.print_help()
        sys.exit(1)
    main(args.file)

