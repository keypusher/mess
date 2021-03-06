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
import subprocess

DEBUG = True
WINDOWS = os.name == 'nt'

def debug(msg):
    if DEBUG:
        with open('debug.log', 'a') as fi:
            fi.write(str(msg).rstrip() + '\n')

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

        #DIV_CHAR = '_'
        self.pagers = []
        widgets = []
        rows = ((getheight() + 1) / len(files))
        self.search = None
        for file_path in files:
            pager = Pager(file_path, rows)
            pager_ui = PagerUI(pager)
            self.pagers.append((pager, pager_ui))
            widgets.append(('weight', 1, pager_ui))
        #searchBox = SearchBox(self.search)
        #widgets.append(('weight', 1, searchBox))
        self.window = urwid.Pile(widgets)

    def search(self, text):
        debug("SEARCH: %s" % text)

    def run(self):
        palette = [
                ('highlight', 'black', 'white')
        ]
        urwid.MainLoop(self.window, palette, unhandled_input=self.handle_input).run()

    def handle_input(self, key):
        debug("Handle Key: %s" % str(key))
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
                self.window.focus.add_search()
            if key == 'tab':
                self.window.focus.hide_focus()
                self.window.focus_position = (self.window.focus_position + 1) % len(self.window.contents)
                self.window.focus.show_focus()
                debug("Focus: %s" % self.window.focus)

        for pager, widget in self.pagers:
            widget.refresh()

class PagerUI(urwid.LineBox):

    def __init__(self, pager):
        self.pager = pager
        self.text = urwid.Text(self.pager.get_page())
        self.filler = urwid.Filler(urwid.Pile([('pack', self.text)]))
        super(PagerUI, self).__init__(self.filler, self.pager.file_path)

    def set_text(self, text):
        self.text.set_text(text)

    def show_focus(self):
        self.tline = u'u2502'

    def hide_focus(self):
        self.tline = u'u2500'

    def refresh(self):
        self.text.set_text(self.pager.get_page())

    def add_search(self):
        #self.pile.contents.append((SearchBox(self.search), ('weight', 1)))
        debug('adding search')
        #edit = urwid.LineBox(urwid.Edit('test'))
        edit = urwid.Filler(urwid.LineBox(SearchBox(self.search, self.remove_search)))
        self.pile.contents.append((edit, ('weight', 2)))
        self.pile.focus_position = self.pile.focus_position + 1

    def remove_search(self):
        self.pile.contents.pop()

    def search(self, text):
        debug("SEARCH (%s): %s" % (self.pager.file_path, text))
        offsets = []
        try: 
            results = subprocess.check_output(['grep', '-b', text, self.pager.file_path])
            debug(results)
            # comes back with byte-offset and line text, ie:
            # "4201: 'name' : 'FOO'
            # "6814: 'name' : 'FOOBAR'

            for line in results.split('\n'):
                offset = line.split(':')[0]
                if offset != '':
                    offsets.append(int(offset))
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:
                debug("no search results found")
        if offsets:
            self.pager.marker = offsets[0]
            self.refresh()
            self.remove_search()
        debug("Matching search offsets: %s" % offsets)
        return offsets

class SearchBox(urwid.Edit):

    def __init__(self, search_callback, exit_callback):
        self.search_callback = search_callback
        self.exit_callback = exit_callback
        super(SearchBox, self).__init__()

    def keypress(self, size, key):
        if key == 'enter':
            text, _ = self.get_text()
            self.search_callback(text)
        if key == 'esc':
            self.exit_callback()
        if key == 'tab':
            return key
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
            #if DEBUG:
            #    debug(line)
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

