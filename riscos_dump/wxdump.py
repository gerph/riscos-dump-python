"""
WxPython classes for dumping hexadecimal information using the Dump object.

* `DumpGrid` - is an embedable Grid which can be used inside existing frames.
* `DumpFrame` - is a frame containing a grid which automatically resizes and can display
                arbitrary data.
* `DumpFileFrame` - is a subclass of DumpFrame which displays data from a file.
"""

import sys

import wx
import wx.grid as gridlib

import riscos_dump.dump as dump


class WxDumpConfig(object):
    colours = {
            # Grid lines and the cursor
            'grid': ('grey', None),
            'cursor': ('blue', None),

            # Invalid cells
            'invalid': ('white', 'black'),

            # Attributes for the main cells
            'plain': ('white', 'black'),
            'alpha': ('white', 'black'),
            'number': ('white', 'black'),
            'control': ('white', 'slate blue'),
            'topbit': ('white', 'forest green'),

            # Attributes applying to words or halfwords
            'word': ('white', 'black'),
            'halfword': ('white', 'black'),

            # Attributes for the text column
            'text': ('white', 'black'),

            # Attributes for the annotation column
            'annotation': ('white', 'black'),
        }

    # Parameters to pass on to the Dump object
    dump_params = {}

    # Number of characters in the row annotations
    row_annotation_size = 24

    # Menu entries as a list of tuples:
    #   (menu item title, function to call, selection state)
    #   selection state: False for non-check function
    #                    True for selected item
    #   function has the args (grid, dump, chosen)
    #   chosen is the selection state when selected, or None to read state
    # `menu_format` - adds entries that change the format of the display (eg 'show disassembly')
    # `menu_extra` - adds entries that operate on the display
    menu_format = []
    menu_extra = []

    # How many rows we will cache at a time
    row_cache_limit = 400

    # How high the default size of the frame should be
    frame_max_height = 600

    # Status bar enable
    frame_statusbar = False

    # Which of the data width choices are available:
    has_width_1 = True
    has_width_2 = True
    has_width_4 = True

    # Which of the menu operations are available:
    has_goto_address = True
    has_find_string = True

    # Whether the grid lines should be shown between cells
    has_grid = False

    # Whether we show the save data menu option
    has_save_data = True
    default_savedata_filename = 'Dump.bin'

    byte_colour = [0] * 256
    for b in range(256):
        if b < 32 or b == 127:
            colour_name = 'control'
        elif (64 < b < 91) or (96 < b < 122):
            colour_name = 'alpha'
        elif (48 < b < 58):
            colour_name = 'number'
        elif b < 128:
            colour_name = 'plain'
        else:
            colour_name = 'topbit'

        byte_colour[b] = colour_name

    def cell_info(self, offset):
        """
        Information about a given offset, used by the Frame code.

        @param offset:  The offset to get information from

        @return:    Status bar text for this offset, or None
        """
        return None

    def mouse_over(self, offset):
        """
        Called when the mouse is over a new cell.

        @param offset:  Data offset, or None if the pointer has moved out of the grid.
        """
        pass


class WxDumpConfigDark(WxDumpConfig):
    colours = {
            # Grid lines and the cursor
            'grid': ('grey', None),
            'cursor': ('blue', None),

            # Invalid cells
            'invalid': ('black', 'white'),

            # Attributes for the main cells
            'plain': ('black', 'white'),
            'alpha': ('black', 'white'),
            'number': ('black', 'white'),
            'control': ('black', 'sky blue'),
            'topbit': ('black', 'green'),

            # Attributes applying to words or halfwords
            'word': ('black', 'white'),
            'halfword': ('black', 'white'),

            # Attributes for the text column
            'text': ('black', 'white'),

            # Attributes for the annotation column
            'annotation': ('black', 'white'),
        }


class DumpTable(gridlib.GridTableBase):

    def __init__(self, dump, data, config):

        self.config = config
        self.dump = dump
        self.data = data
        super(DumpTable, self).__init__()

        # Attributes applying to bytes
        self.attributes = {}
        colours = self.config.colours
        for (name, cols) in colours.items():
            attr = gridlib.GridCellAttr()
            attr.SetBackgroundColour(cols[0])
            attr.SetTextColour(cols[1])
            self.attributes[name] = attr

        self.align_right = (wx.ALIGN_RIGHT, wx.ALIGN_CENTER)
        self.align_left = (wx.ALIGN_LEFT, wx.ALIGN_CENTER)

        self.headings = [''] * self.dump.columns
        self.column_alignment = []

        # We keep a cache of the row data we've read from the Dump object, but discard once
        # we reache this limit.
        self.row_cache_limit = config.row_cache_limit
        self.row_cache = {}

        self.update_content()

    def update_content(self):
        self.headings = self.dump.data_headings()
        self.column_alignment = [self.align_right] * self.dump.columns

        if self.dump.text:
            self.headings.append(self.dump.text_label)
            self.column_alignment.append(self.align_left)

        if self.dump.annotations:
            self.headings.append(self.dump.annotation_label)
            self.column_alignment.append(self.align_left)

    def GetNumberRows(self):
        rowsize = self.dump.columns * self.dump.width
        return int((len(self.data) + rowsize - 1) / rowsize)

    def GetNumberCols(self):
        columns = self.dump.columns + 1
        if self.dump.annotations:
            columns += 1
        return columns

    def IsEmptyCell(self, row, col):
        if col >= self.dump.columns:
            # The text/annotation column is always valid
            return False
        (rowvalues, rowtext, rowannotation) = self.setup_row(row)
        if not rowvalues:
            return True
        return rowvalues[col] is None

    def GetColLabelValue(self, col):
        if col < len(self.headings):
            return self.headings[col]
        else:
            return ''

    def GetRowLabelValue(self, row):
        return self.dump.format_address(self.dump.row_to_offset(row)).upper()

    def GetCellAlignment(self, row, col):
        return self.column_alignment[col]

    def GetAttr(self, row, col, kind):
        (rowvalues, rowtext, rowannotation) = self.setup_row(row)
        if not rowvalues:
            attr = self.attributes['invalid']
        else:
            if col == self.dump.columns:
                attr = self.attributes['text']
            elif col == self.dump.columns + 1:
                attr = self.attributes['annotation']
            else:
                if self.dump.width == 1:
                    value = rowvalues[col]
                    if value is None:
                        colour_name = 'invalid'
                    else:
                        colour_name = self.config.byte_colour[value]
                    attr = self.attributes[colour_name]
                elif self.dump.width == 4:
                    attr = self.attributes['word']
                elif self.dump.width == 2:
                    attr = self.attributes['halfword']
                else:
                    attr = self.attributes['invalid']
        attr.IncRef()
        return attr

    def GetValue(self, row, col):
        (rowvalues, rowtext, rowannotation) = self.setup_row(row)
        if not rowvalues:
            return '<invalid>'

        if col < self.dump.columns:
            width = self.dump.width
            value = rowvalues[col]
            if value is None:
                return None
            if width == 1:
                return '{:02X}'.format(value)
            elif width == 4:
                return '{:08X}'.format(value)
            elif width == 2:
                return '{:04X}'.format(value)
            return value
        elif col == self.dump.columns:
            return rowtext
        else:
            return rowannotation

    def setup_row(self, row):
        if row not in self.row_cache:

            rowdata = self.dump.row_data(row)
            if not rowdata:
                # No data, so these cells are empty
                rowvalues = [None] * self.dump.columns
                rowtext = ''
                rowannotation = ''
            else:

                rowvalues = self.dump.row_values(row)
                if len(rowvalues) < self.dump.columns:
                    if not isinstance(rowvalues, list):
                        rowvalues = list(rowvalues)
                    rowvalues += [None] * (self.dump.columns - len(rowvalues))

                rowbytevalues = [c for c in rowdata]
                rowtext = self.dump.format_chars(rowbytevalues)
                rowannotation = self.dump.format_annotation(row)

            if len(self.row_cache) > self.row_cache_limit:
                # Reset the cache so that we don't accumulate forever
                #print("Clear row cache")
                self.row_cache = {}

            self.row_cache[row] = (rowvalues, rowtext, rowannotation)

        return self.row_cache[row]

    def SetData(self, data):
        self.dump.data = data
        self.row_cache = {}


class DumpStatusBar(wx.StatusBar):

    def __init__(self, parent):
        super(DumpStatusBar, self).__init__(parent, -1)
        # Nothing special to do here?


class DumpCellRenderer(wx.grid.GridCellStringRenderer):
    """
    Custom cell renderer for drawing the text cells in different colours.

    If the 'text' in the cell has been returned as a sequence of pairs of (colour, text)
    then we'll render the strings in that format. This is intended to be used to draw
    text or attribution cells with colouring.
    """

    def __init__(self, *args, **kwargs):
        super(DumpCellRenderer, self).__init__(*args, **kwargs)
        self.cached_colours = {}

    def Draw(self, grid, attr, dc, rect, row, col, isSelected):
        text = grid.table.GetValue(row, col)
        if not isinstance(text, (tuple, list)):
            super(DumpCellRenderer, self).Draw(grid, attr, dc, rect, row, col, isSelected)
        else:
            (hAlign, vAlign) = attr.GetAlignment()

            if isSelected:
                bg = grid.GetSelectionBackground()
                fg = grid.GetSelectionForeground()
            else:
                bg = attr.BackgroundColour
                fg = attr.TextColour

            dc.SetBrush(wx.Brush(bg, wx.SOLID))
            dc.SetPen(wx.Pen(bg))
            dc.DrawRectangle(rect)

            dc.SetTextBackground(attr.BackgroundColour)
            dc.SetFont(attr.GetFont())

            for part in text:
                if isinstance(part, (str, unicode)):
                    dc.SetTextForeground(attr.TextColour)
                    textpart = part
                else:
                    colname = part[0]
                    textpart = part[1]
                    col = self.cached_colours.get(colname, None)
                    if not col:
                        col = wx.Colour(colname)
                        self.cached_colours[colname] = col
                    dc.SetTextForeground(col)

                grid.DrawTextRectangle(dc, textpart, rect, hAlign, vAlign)
                (w, h) = dc.GetTextExtent(textpart)
                rect.x += w
                rect.width -= w


class DumpGrid(gridlib.Grid):

    def __init__(self, parent, data, config=None):
        super(DumpGrid, self).__init__(parent, -1, style=wx.VSCROLL)

        self.config = config or WxDumpConfig()
        self.parent = parent
        self.menu_items = []

        self.dump = dump.DumpBase()
        self.dump.data = data
        for key, value in self.config.dump_params.items():
            if getattr(self.dump, key, Ellipsis) is Ellipsis:
                raise AttributeError("Dump parameter '{}' is not recognised".format(key))
            setattr(self.dump, key, value)

        self.text_column = self.dump.columns
        self.annotation_column = self.dump.columns + 1

        self.table = DumpTable(self.dump, self.dump.data, self.config)
        self.SetTable(self.table, True)

        cursor_colour = self.table.attributes['cursor'].BackgroundColour
        self.SetCellHighlightColour(cursor_colour)
        grid_colour = self.table.attributes['grid'].BackgroundColour
        self.SetGridLineColour(grid_colour)

        self.cellfont = wx.Font(12, wx.TELETYPE, wx.NORMAL, wx.NORMAL)
        self.SetDefaultCellFont(self.cellfont)
        self.SetLabelFont(wx.Font(12, wx.TELETYPE, wx.NORMAL, wx.FONTWEIGHT_BOLD))

        self.EnableEditing(False)
        self.EnableDragRowSize(False)
        self.EnableDragColSize(False)
        self.EnableGridLines(self.config.has_grid)
        self.SetRowLabelAlignment(wx.ALIGN_RIGHT, wx.ALIGN_CENTER)

        self.SetDefaultRenderer(DumpCellRenderer())

        self.cellsize = (16 * 2, 16)
        self.labelsize = (16 * 8, 16)
        self.textsize = (16 * 16, 16)
        self.annotationsize = (24 * 16, 16)
        self.min_width = 16
        self.min_height = 16
        self.resize()

        self.last_mouse_over = None
        self.grid_window = self.GetGridWindow()
        self.grid_window.Bind(wx.EVT_MOTION, self.on_mouse_over)
        self.grid_window.Bind(wx.EVT_LEAVE_WINDOW, self.on_mouse_out)
        self.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.on_select_cell)

        # Build up the menu we'll use
        self.menu = wx.Menu()

        self.last_find_string = ''

        self.add_menu_format(self.menu)
        self.add_menu_extra(self.menu)

        if self.config.has_save_data:
            if self.menu.GetMenuItemCount() > 0:
                self.menu.AppendSeparator()
            self.item_savedata = self.menu.Append(-1, "Save data...")
            self.Bind(wx.EVT_MENU, self.on_save_data, self.item_savedata)
        else:
            self.item_savedata = None

        self.Bind(gridlib.EVT_GRID_CELL_RIGHT_CLICK, self.on_popup_menu)
        self.Bind(wx.EVT_KEY_DOWN, self.on_key)

    def FindString(self, s):
        """
        Find a string in the data and go to it.

        @param s: String to look for

        @return:    True if address is valid, False if outside our range
        """
        cursor = self.GetAddress() - self.dump.address_base
        index = self.dump.data.find(s, cursor + 1)
        if index == -1:
            # not found after the current cursor, so look from the start
            index = self.dump.data.find(s)
            if index == -1:
                # Not found at the start either
                return False

        address = self.dump.address_base + index
        (row, col) = self.dump.address_to_coords(address)
        if row is None:
            return False

        self.GoToCell(row, col)
        return True

    def GotoAddress(self, address):
        """
        Go to a specific address.

        @param address: Address to go to

        @return:    True if address is valid, False if outside our range
        """
        (row, col) = self.dump.address_to_coords(address)
        if row is None:
            return False

        self.GoToCell(row, col)
        return True

    def GetAddress(self):
        """
        Read the current cursor position.

        @return: Current address
        """
        col = self.GetGridCursorCol()
        row = self.GetGridCursorRow()
        address = self.dump.coords_to_address(row, col, bound=True)
        return address

    def add_menu_format(self, menu):
        """
        Add the items that change the format of the dump display.
        """
        if self.config.has_width_1:
            self.item_bytes = menu.Append(-1, "Bytes", kind=wx.ITEM_CHECK)
            self.Bind(wx.EVT_MENU, lambda event: self.SetDumpWidth(1), self.item_bytes)
        else:
            self.item_bytes = None

        if self.config.has_width_2:
            self.item_halfwords = menu.Append(-1, "Half words", kind=wx.ITEM_CHECK)
            self.Bind(wx.EVT_MENU, lambda event: self.SetDumpWidth(2), self.item_halfwords)
        else:
            self.item_halfwords = None

        if self.config.has_width_4:
            self.item_words = menu.Append(-1, "Words", kind=wx.ITEM_CHECK)
            self.Bind(wx.EVT_MENU, lambda event: self.SetDumpWidth(4), self.item_words)
        else:
            self.item_words = None

        if self.config.menu_format:
            if self.menu.GetMenuItemCount() > 0:
                menu.AppendSeparator()
            for item in self.config.menu_format:
                name = item[0]
                func = item[1]
                if len(item) > 2:
                    checked = item[2]
                else:
                    checked = False
                menuitem = self.menu.Append(-1, name, kind=wx.ITEM_NORMAL if not checked else wx.ITEM_CHECK)
                self.menu_items.append((menuitem, name, func, checked))
                self.Bind(wx.EVT_MENU, lambda event, func=func: func(self, self.dump, chosen=True), menuitem)

    def add_menu_extra(self, menu):
        if self.config.has_goto_address or self.config.has_find_string or self.config.menu_extra:
            if self.menu.GetMenuItemCount() > 0:
                menu.AppendSeparator()

        if self.config.has_goto_address:
            name = "Goto address...\tctrl+L"
            func = self.on_goto_address
            menuitem = self.menu.Append(-1, name, kind=wx.ITEM_NORMAL)
            self.menu_items.append((menuitem, name, func, False))
            self.Bind(wx.EVT_MENU, func, menuitem)

        if self.config.has_find_string:
            name = "Find string...\tctrl+F"
            func = self.on_find_string
            menuitem = self.menu.Append(-1, name, kind=wx.ITEM_NORMAL)
            self.menu_items.append((menuitem, name, func, False))
            self.Bind(wx.EVT_MENU, func, menuitem)

        if self.config.menu_extra:
            for item in self.config.menu_extra:
                name = item[0]
                func = item[1]
                if len(item) > 2:
                    checked = item[2]
                else:
                    checked = False
                menuitem = self.menu.Append(-1, name, kind=wx.ITEM_NORMAL if not checked else wx.ITEM_CHECK)
                self.menu_items.append((menuitem, name, func, checked))
                self.Bind(wx.EVT_MENU, lambda event, func=func: func(self, self.dump, chosen=True), menuitem)

    def on_key(self, event):
        if self.config.has_find_string:
            if event.ControlDown() and event.GetKeyCode() == ord('F'):
                self.on_find_string(event)
        if self.config.has_goto_address:
            if event.ControlDown() and event.GetKeyCode() == ord('L'):
                self.on_goto_address(event)
        event.Skip()

    def on_select_cell(self, event):
        row = event.Row
        col = event.Col
        if col >= self.dump.columns:
            col = self.dump.columns - 1
            # Reject selecting the text/annotations, and instead go to the end most data cell in that row
            event.Veto()
            self.GoToCell(row, col)

    def on_popup_menu(self, event):
        if self.item_bytes:
            self.item_bytes.Check(self.dump.width == 1)
        if self.item_halfwords:
            self.item_halfwords.Check(self.dump.width == 2)
        if self.item_words:
            self.item_words.Check(self.dump.width == 4)

        for extra in self.menu_items:
            if extra[3]:
                # This is a checkable box.
                menuitem = extra[0]
                func = extra[2]
                state = func(self, self.dump, chosen=False)
                menuitem.Check(state)

        self.PopupMenu(self.menu)

    def on_mouse_over(self, event):
        pos = self.CalcUnscrolledPosition(event.GetX(), event.GetY())
        cell_pos = self.XYToCell(pos)
        if self.last_mouse_over != cell_pos:
            self.last_mouse_over = cell_pos
            if cell_pos.Col >= self.dump.columns:
                # They're over the text column
                offset = None
            else:
                offset = self.dump.row_to_offset(cell_pos.Row) + cell_pos.Col * self.dump.width
                if offset >= len(self.dump.data):
                    offset = None
            self.config.mouse_over(offset)

    def on_mouse_out(self, event):
        self.last_mouse_over = None
        self.config.mouse_over(None)

    def on_goto_address(self, event):
        start = self.dump.address_base
        end = self.dump.address_base + len(self.dump.data)
        address = self.GetAddress()

        address_str = wx.GetTextFromUser("Address to go to (&{:X} - &{:X}):".format(start, end),
                                         caption="Goto address",
                                         default_value="&{:X}".format(address),
                                         parent=self, centre=True)

        if not address_str:
            # If they didn't give anything, just ignore as if they cancelled it.
            return

        if address_str[0] == '&':
            address_str = address_str[1:]
        if address_str[0:1] == '0x':
            address_str = address_str[1:]

        try:
            address = int(address_str, 16)
            self.GotoAddress(address)
        except ValueError:
            # FIXME: Make this report an error?
            pass

    def on_find_string(self, event):
        find_str = wx.GetTextFromUser("Find string (case-sensitive):",
                                      caption="Find string",
                                      default_value=self.last_find_string,
                                      parent=self, centre=True)

        if not find_str:
            # If they didn't give anything, just ignore as if they cancelled it.
            return

        self.last_find_string = find_str

        # FIXME: Should this be UTF-8 encoded? or should we provide a conversion function?
        self.FindString(find_str.encode('utf-8'))

    def on_save_data(self, event):
        if self.config.default_savedata_filename.endswith('.bin'):
            wildcard = "Binary files (*.bin)|*.bin"
        else:
            wildcard = "All files|*"
        with wx.FileDialog(self,
                           "Save data",
                           wildcard=wildcard,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialogue:
            dialogue.SetFilename(self.config.default_savedata_filename)
            dialogue.SetDirectory('.')
            if dialogue.ShowModal() == wx.ID_CANCEL:
                # Screensave was aborted
                return

            # save the current contents in the file
            filename = dialogue.GetPath()
            if isinstance(filename, unicode):
                filename = filename.encode('utf-8')

            with open(filename, 'wb') as fh:
                if sys.version_info.major == 3:
                    data = bytes(self.dump.data)
                else:
                    # Python 2 doesn't have the calls to __bytes__ for bytes operations,
                    # so we must do this ourselves.
                    data = self.dump.data
                    if not isinstance(data, bytes):
                        if getattr(self.dump.data, '__bytes__', None):
                            data = self.dump.data.__bytes__()
                        else:
                            data = data[0:len(data)]
                fh.write(data)

    def GetVisibleRange(self):
        # Get the position of the visible cells
        ux, uy = self.GetScrollPixelsPerUnit()
        sx, sy = self.GetViewStart()
        w, h = self.GetGridWindow().GetClientSize().Get()
        sx *= ux
        sy *= uy

        x0 = max(self.XToCol(sx), 0)
        y0 = max(self.YToRow(sy), 0)
        x1 = min(self.XToCol(sx + w, True), self.table.GetNumberCols() - 1)
        y1 = min(self.YToRow(sy + h, True), self.table.GetNumberRows() - 1)

        return (x0, y0, x1, y1)

    def ScrollToRow(self, row):
        ux, uy = self.GetScrollPixelsPerUnit()
        (x0, y0, x1, y1) = self.CellToRect(row, 0)
        self.Scroll(x0 / ux, y0 / uy)

    def SetDumpWidth(self, width):
        self.dump.columns = int(self.dump.width * self.dump.columns / width)
        self.dump.width = width

        self.table = DumpTable(self.dump, self.dump.data, config=self.config)
        self.SetTable(self.table, True)
        self.resize()
        self.parent.resize()

    def SetDumpColumns(self, columns):
        self.dump.columns = columns

        self.table = DumpTable(self.dump, self.dump.data, config=self.config)
        self.SetTable(self.table, True)
        self.resize()
        self.parent.resize()

    def SetData(self, data):
        self.table.SetData(data)
        self.ForceRefresh()

    def resize(self):
        self.text_column = self.dump.columns
        self.annotation_column = self.dump.columns + 1

        self.BeginBatch()

        dc = wx.ScreenDC()
        dc.SetFont(self.cellfont)
        self.labelsize = dc.GetTextExtent('M' * 9)
        self.cellsize = dc.GetTextExtent('0' * (self.dump.width * 2 + 1))
        self.textsize = dc.GetTextExtent('M' * (self.dump.width * self.dump.columns + 1))
        self.annotationsize = dc.GetTextExtent('M' * (self.config.row_annotation_size + 1))
        # FIXME: This is wrong, but it's about the right sort of size
        self.scrollbarsize = dc.GetTextExtent('M' * 2)[0]

        # Set the column widths
        colsizes = []
        for col in range(self.dump.columns):
            colsizes.append(self.cellsize[0])
        colsizes.append(self.textsize[0])
        if self.dump.annotations:
            colsizes.append(self.annotationsize[0])
        colsizes[-1] += self.scrollbarsize

        for col, size in enumerate(colsizes):
            self.SetColSize(col, size)

        # The column lable height
        self.SetColLabelSize(int(self.cellsize[1] * 1.5))

        self.min_height = int(self.textsize[1] * 1.5)

        self.SetRowLabelSize(self.labelsize[0])
        self.min_width = self.labelsize[0]

        self.EndBatch()
        self.AdjustScrollbars()

        self.ForceRefresh()
        self.Layout()

        self.InvalidateBestSize()
        (width, height) = self.GetBestSize()
        dx = wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X)
        self.SetMaxSize((width + dx, height))

    def GetMinSize(self):
        return wx.Size(self.min_width, self.min_height)

    def GetBestSize(self):
        rect = self.CellToRect(self.table.GetNumberRows() - 1, self.table.GetNumberCols() - 1)
        cells_width = rect.Right + self.labelsize[0]
        cells_height = rect.Bottom + int(self.cellsize[1] * 1.5) + 1

        # Don't allow the window to have a very small minimum size
        cells_height = max(cells_height, 32 + self.labelsize[1] + self.textsize[1] * 2)
        cells_width = max(cells_width, 32 + self.labelsize[0] + self.textsize[0])
        return wx.Size(cells_width,
                       cells_height)


class DumpFrame(wx.Frame):
    """
    A Frame which can display arbitrary data.
    """

    def __init__(self, title="Hex Dumper", data=b'', config=None):

        self.config = config or WxDumpConfig()
        self.data = data
        super(DumpFrame, self).__init__(None, -1, title=title)

        data = self.GetDumpData()

        self.statusbar = None
        self.statusbar_height = 0
        if self.config.frame_statusbar:
            self.statusbar = DumpStatusBar(self)
            self.SetStatusBar(self.statusbar)
            config.mouse_over = self.update_statusbar
            self.statusbar_height = self.statusbar.GetSize()[1]

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.grid = DumpGrid(self, data, config=config)
        sizer.Add(self.grid)
        self.SetSizer(sizer)

        self.resize()

    def resize(self):
        (best_width, best_height) = self.grid.GetBestSize()
        limit_height = min(best_height, self.config.frame_max_height)
        self.SetMaxClientSize((best_width, best_height))

        self.SetClientSize(best_width, limit_height)

        (min_width, min_height) = self.grid.GetMinSize()
        self.SetMinClientSize(wx.Size(min_width, min_height + self.statusbar_height))

    def update_statusbar(self, offset):
        """
        Called when the mouse is over a new cell.

        @param offset:  Data offset, or None if the pointer has moved out of the grid.
        """
        if offset is None:
            self.statusbar.SetStatusText('')
        else:
            self.statusbar.SetStatusText(self.config.cellinfo(offset))

    def GetDumpData(self):
        # FIXME: Might be wrong if we refreshed? Read from the grid?
        return self.data


class DumpFileFrame(DumpFrame):
    """
    A Frame which can display data taken from a file.
    """

    def __init__(self, filename, *args, **kwargs):
        self.filename = filename
        super(DumpFileFrame, self).__init__(*args, **kwargs)

    def GetDumpData(self):
        fh = open(self.filename, 'rb')
        data = dump.FileDataSource(fh)
        return data
