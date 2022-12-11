from client_utils import error_handler
import curses
from datetime import datetime
import time
import traceback


class TextPad(object):
    # use this as a virtual notepad
    # write a large amount of data to it, then display a section of it on the screen
    # to have a border, use another window with a border
    def __init__(self, name, rows, columns, y1, x1, y2, x2, ShowBorder, BorderColor, stdscr):
        self.name = name
        self.rows = rows
        self.columns = columns
        self.y1 = y1  # These are coordinates for the window corners on the screen
        self.x1 = x1  # These are coordinates for the window corners on the screen
        self.y2 = y2  # These are coordinates for the window corners on the screen
        self.x2 = x2  # These are coordinates for the window corners on the screen
        self.ShowBorder = ShowBorder
        self.BorderColor = BorderColor  # pre defined text colors 1-7
        self.TextPad = curses.newpad(self.rows, self.columns)
        self.PreviousLineColor = 2
        self.stdscr = stdscr

    def pad_print(self, PrintLine, Color=2, TimeStamp=False):
        # print to the pad
        try:
            self.TextPad.idlok(1)
            self.TextPad.scrollok(1)

            current_time = datetime.now().strftime("%H:%M:%S")
            if (TimeStamp):
                PrintLine = current_time + ": " + PrintLine

            # expand tabs to X spaces, pad the string with space then truncate
            PrintLine = PrintLine.expandtabs(4)
            PrintLine = PrintLine.ljust(self.columns, ' ')

            self.TextPad.attron(curses.color_pair(Color))
            self.TextPad.addstr(PrintLine)
            self.TextPad.attroff(curses.color_pair(Color))

            # We will refresh after a series of calls instead of every update
            self.TextPad.refresh(0, 0, self.y1, self.x1,
                                 self.y1 + self.rows, self.x1 + self.columns)

        except Exception as ErrorMessage:
            time.sleep(2)
            TraceMessage = traceback.format_exc()
            AdditionalInfo = "PrintLine: " + PrintLine
            error_handler(ErrorMessage, TraceMessage, AdditionalInfo, self.stdscr)

    def clear(self):
        try:
            self.TextPad.erase()
            self.TextPad.refresh(0, 0, self.y1, self.x1, self.y1 + self.rows, self.x1 + self.columns)
        except Exception as ErrorMessage:
            TraceMessage = traceback.format_exc()
            AdditionalInfo = "erasing textpad"
            error_handler(ErrorMessage, TraceMessage, AdditionalInfo, self.stdscr)
