"""
Python Line EDiting
"""
# Python 2 compatibility
from __future__ import print_function, unicode_literals
__metaclass__ = type

import os
import sys

class TermIO:
    def __init__(self):
        self.queue = []
        self._getch = self._getgetch()
    def _getgetch(self):
        try:
            from msvcrt import getch
        except ImportError:
            import tty, termios
            def getch():
                infile = sys.stdin.fileno()
                old_settings = termios.tcgetattr(infile)
                try:
                    tty.setraw(infile)
                    return sys.stdin.read(1)
                finally:
                    termios.tcsetattr(infile, termios.TCSADRAIN, old_settings)
            return getch
    def getch(self):
        if len(self.queue):
            return self.queue.pop()
        else:
            return self._getch()
    def putch(self, ch):
        self.queue.append(ch)
_TermIO = TermIO()
getch = _TermIO.getch
putch = _TermIO.putch

def getTerminalWidth():
    def screen_size(fd):
        try:
            import fcntl, termios, struct
            cr = struct.unpack(b'hh', fcntl.ioctl(fd, termios.TIOCGWINSZ,
        '1234'))
        except Exception:
            return
        return cr
    cr = screen_size(0) or screen_size(1) or screen_size(2)
    if not cr:
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            cr = screen_size(fd)
            os.close(fd)
        except:
            pass
    if not cr:
        cr = (None, os.environ.get('COLUMNS', 80))
    return cr[1]

class Reader:
    def __new__(cls, **kwargs):
        if cls is not Reader:
            # Don't re-run this on instances of subclasses
            return object.__new__(cls)
        if 'infile' not in kwargs:
            kwargs['infile'] = sys.stdin
        infile = kwargs['infile']
        tty = True
        try:
            if not infile.isatty():
                tty = False
        except (TypeError, AttributeError):
            raise TypeError('infile is not a valid file-like object')
        if not tty:
            return BasicReader(**kwargs)
        else:
            return TTYReader(**kwargs)

class TTYReader(Reader):
    def __init__(self, **kwargs):
        # Only reads from sys.stdin
        # This is not used internally, but is kept for clarity
        self.infile = sys.stdin
        self.prompt = kwargs['prompt'] if 'prompt' in kwargs else ''
        self.current_line = ''
        self.cursor_pos = 0
        self.hooks = {
            chr(i):[] + (TTYReaderDefaultHooks[chr(i)] if chr(i) in TTYReaderDefaultHooks else [])
            for i in range(256)}
    
    def attach_hooks(self, hooks):
        for ch in hooks:
            if ch not in self.hooks:
                self.hooks[ch] = []
            self.hooks[ch].extend(hooks[ch])
    
    def reset(self):
        self.current_line = ''
        self.cursor_pos = 0
        sys.stdout.write('\r')
    
    def display(self):
        width = getTerminalWidth()
        line = self.current_line
        sys.stdout.write('\r' + (' ' * width) + '\r')
        sys.stdout.write(self.prompt)
        start = -width + len(self.prompt) + 1
        #if len(line) + len(self.prompt) > width:
        #    start = len(line) - width - len(self.prompt)
        sys.stdout.write(line[start:])
        sys.stdout.write('\r' + ('\x1b[C' * min(width, self.cursor_pos + len(self.prompt))))
        sys.stdout.flush()
    
    def readline(self, strip=True):
        line = ''
        char = ''
        self.display()
        while not self.current_line.endswith('\n'):
            self.parse()
        line = self.current_line
        self.reset()
        if strip:
            line = line.rstrip('\n')
        return line

    def parse(self):
        #while 1:
        ch = getch()
        if ord(ch) < 128:
            if ch == '\r':
                ch = '\n'
            self.ch = ch
            success = True
            for hook in self.hooks[ch]:
                result = hook(self)
                if result is False:
                    success = False
            ch = self.ch
            del self.ch
            if success and ord(ch) >= 32 and ord(ch) < 127:
                self.current_line = self.current_line[:self.cursor_pos] + ch + self.current_line[self.cursor_pos:]
                self.cursor_pos += 1
            if ch == '\n':
                self.current_line += '\n'
            self.cursor_pos = max(0, min(self.cursor_pos, len(self.current_line)))
        self.display()

class TTYReaderHooks:
    @staticmethod
    def beginning(reader):
        reader.cursor_pos = 0
        return True

    @staticmethod
    def end(reader):
        reader.cursor_pos = len(reader.current_line)
        return True

    @staticmethod
    def interrupt(reader):
        reader.current_line = ''
        sys.stdout.write('\n')
        return False
    
    @staticmethod
    def eof(reader):
        raise EOFError

    @staticmethod
    def kill_right(reader):
        reader.current_line = reader.current_line[:reader.cursor_pos]
        return True

    @staticmethod
    def kill_left(reader):
        reader.current_line = reader.current_line[reader.cursor_pos:]
        reader.cursor_pos = 0
        return True

    @staticmethod
    def swap(reader):
        if reader.cursor_pos >= len(reader.current_line):
            reader.cursor_pos -= 1
        pos, line = reader.cursor_pos, reader.current_line
        if pos == 0:
            return
        reader.current_line = line[:pos-1] + line[pos] + line[pos-1] + line[pos+1:]
        reader.cursor_pos += 1
        return True

    @staticmethod
    def handle_escape(reader):
        ch = getch()
        if ch == '[':
            ch = getch()
            if ch == 'C':
                reader.cursor_pos += 1
            elif ch == 'D':
                reader.cursor_pos -= 1
        elif ch in 'bf':
            d = 2 * (ch == 'f') - 1
            reader.cursor_pos += 10*d

    @staticmethod
    def quit(reader):
        print('\n')
        sys.exit(1)

    @staticmethod
    def delete(reader):
        if reader.cursor_pos == 0:
            return
        reader.current_line = reader.current_line[:reader.cursor_pos - 1] + \
            reader.current_line[reader.cursor_pos:]
        reader.cursor_pos -= 1
        return True
    

TTYReaderDefaultHooks = {
    '\x01': [TTYReaderHooks.beginning],
    '\x05': [TTYReaderHooks.end],
    '\x03': [TTYReaderHooks.interrupt],
    '\x04': [TTYReaderHooks.eof],
    '\x0b': [TTYReaderHooks.kill_right],
    '\x15': [TTYReaderHooks.kill_left],
    '\x14': [TTYReaderHooks.swap],
    '\x1b': [TTYReaderHooks.handle_escape],
    '\x1c': [TTYReaderHooks.quit],
    '\x7f': [TTYReaderHooks.delete],
}

class BasicReader(Reader):
    def __init__(self, **kwargs):
        self.infile = kwargs['infile'] if 'infile' in kwargs else sys.stdin
    
    def readline(self, strip=True):
        line = self.infile.readline().replace('\r', '')
        if len(line) == 0:
            raise EOFError
        if strip:
            line = line.rstrip('\n')
        return line

DefaultReader = Reader()
readline = DefaultReader.readline
