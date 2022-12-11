from client_utils import error_handler
import curses
from datetime import datetime
import traceback


class TextWindow(object):
    def __init__(self, name, rows, columns, y1, x1, y2, x2, ShowBorder, BorderColor, TitleColor, stdscr):
        self.name = name
        self.rows = rows
        self.columns = columns
        self.y1 = y1
        self.x1 = x1
        self.y2 = y2
        self.x2 = x2
        self.ShowBorder = ShowBorder
        self.BorderColor = BorderColor  # pre defined text colors 1-7
        self.TextWindow = curses.newwin(
            self.rows, self.columns, self.y1, self.x1)
        self.CurrentRow = 1
        self.StartColumn = 1
        # we will modify this later, based on if we show borders or not
        self.DisplayRows = self.rows
        # we will modify this later, based on if we show borders or not
        self.DisplayColumns = self.columns
        self.PreviousLineText = ""
        self.PreviousLineRow = 0
        self.PreviousLineColor = 2
        self.Title = ""
        self.TitleColor = TitleColor
        self.stdscr = stdscr

        # If we are showing border, we only print inside the lines
        if (self.ShowBorder == 'Y'):
            self.CurrentRow = 1
            self.StartColumn = 1
            self.DisplayRows = self.rows - 2  # we don't want to print over the border
            # we don't want to print over the border
            self.DisplayColumns = self.columns - 2
            self.TextWindow.attron(curses.color_pair(BorderColor))
            self.TextWindow.border()
            self.TextWindow.attroff(curses.color_pair(BorderColor))
            self.TextWindow.refresh()

        else:
            self.CurrentRow = 0
            self.StartColumn = 0

    def scroll_print(self, PrintLine, Color=2, TimeStamp=False, BoldLine=True):
        # print(PrintLine)
        # for now the string is printed in the window and the current row is incremented
        # when the counter reaches the end of the window, we will wrap around to the top
        # we don't print on the window border
        # make sure to pad the new string with spaces to overwrite any old text

        current_time = datetime.now().strftime("%H:%M:%S")

        if (TimeStamp):
            PrintLine = current_time + ": {}".format(PrintLine)

        # expand tabs to X spaces, pad the string with space
        PrintLine = PrintLine.expandtabs(4)

        # adjust strings
        # Get a part of the big string that will fit in the window
        PrintableString = PrintLine[0:self.DisplayColumns]
        RemainingString = PrintLine[self.DisplayColumns+1:]

        try:

            while (len(PrintableString) > 0):

                # padd with spaces
                PrintableString = PrintableString.ljust(
                    self.DisplayColumns, ' ')

                # if (self.rows == 1):
                #  #if you print on the last character of a window you get an error
                #  PrintableString = PrintableString[0:-2]
                #  self.TextWindow.addstr(0,0,PrintableString)
                # else:

                # unbold Previous line
                self.TextWindow.attron(
                    curses.color_pair(self.PreviousLineColor))
                self.TextWindow.addstr(
                    self.PreviousLineRow, self.StartColumn, self.PreviousLineText)
                self.TextWindow.attroff(
                    curses.color_pair(self.PreviousLineColor))

                if BoldLine:
                    # A_NORMAL        Normal display (no highlight)
                    # A_STANDOUT      Best highlighting mode of the terminal
                    # A_UNDERLINE     Underlining
                    # A_REVERSE       Reverse video
                    # A_BLINK         Blinking
                    # A_DIM           Half bright
                    # A_BOLD          Extra bright or bold
                    # A_PROTECT       Protected mode
                    # A_INVIS         Invisible or blank mode
                    # A_ALTCHARSET    Alternate character set
                    # A_CHARTEXT      Bit-mask to extract a character
                    # COLOR_PAIR(n)   Color-pair number n

                    # print new line in bold
                    self.TextWindow.attron(curses.color_pair(Color))
                    self.TextWindow.addstr(
                        self.CurrentRow, self.StartColumn, PrintableString, curses.A_BOLD)
                    self.TextWindow.attroff(curses.color_pair(Color))
                else:
                    # print new line in Regular
                    self.TextWindow.attron(curses.color_pair(Color))
                    self.TextWindow.addstr(
                        self.CurrentRow, self.StartColumn, PrintableString)
                    self.TextWindow.attroff(curses.color_pair(Color))

                self.PreviousLineText = PrintableString
                self.PreviousLineColor = Color
                self.PreviousLineRow = self.CurrentRow
                self.CurrentRow = self.CurrentRow + 1

                # Adjust strings
                PrintableString = RemainingString[0:self.DisplayColumns]
                RemainingString = RemainingString[self.DisplayColumns:]

            if (self.CurrentRow > (self.DisplayRows)):
                if (self.ShowBorder == 'Y'):
                    self.CurrentRow = 1
                else:
                    self.CurrentRow = 0

            # erase to end of line
            # self.TextWindow.clrtoeol()
            self.TextWindow.refresh()

        except Exception as ErrorMessage:
            TraceMessage = traceback.format_exc()
            AdditionalInfo = "PrintLine: {}".format(PrintLine)

            error_handler(ErrorMessage, TraceMessage, AdditionalInfo, self.stdscr)

    def window_print(self, y, x, PrintLine, Color=2):
        # print at a specific coordinate within the window
        # try:

        # expand tabs to X spaces, pad the string with space then truncate
        PrintLine = PrintLine.expandtabs(4)

        # pad the print line with spaces then truncate at the display length
        PrintLine = PrintLine.ljust(self.DisplayColumns - 1)
        PrintLine = PrintLine[0:self.DisplayColumns - x]

        self.TextWindow.attron(curses.color_pair(Color))
        self.TextWindow.addstr(y, x, PrintLine)
        self.TextWindow.attroff(curses.color_pair(Color))

        self.TextWindow.refresh()

    def display_title(self):
        # display the window title

        title = ''

        try:
            # expand tabs to X spaces, pad the string with space then truncate
            title = self.Title[0:self.DisplayColumns-3]

            self.TextWindow.attron(curses.color_pair(self.TitleColor))
            if (self.rows > 2):
                # print new line in bold
                self.TextWindow.addstr(0, 2, title)
            else:
                print("ERROR - You cannot display title on a window smaller than 3 rows")

            self.TextWindow.attroff(curses.color_pair(self.TitleColor))
            self.TextWindow.refresh()

        except Exception as ErrorMessage:
            TraceMessage = traceback.format_exc()
            AdditionalInfo = "Title: " + title
            error_handler(ErrorMessage, TraceMessage, AdditionalInfo, self.stdscr)

    def clear(self):
        self.TextWindow.erase()
        self.TextWindow.attron(curses.color_pair(self.BorderColor))
        self.TextWindow.border()
        self.TextWindow.attroff(curses.color_pair(self.BorderColor))
        self.display_title()

        if self.ShowBorder == 'Y':
            self.CurrentRow = 1
            self.StartColumn = 1
        else:
            self.CurrentRow = 0
            self.StartColumn = 0
