"""
WxPython classes for dumping hexadecimal information using the Dump object.

* `DumpGrid` - is an embedable Grid which can be used inside existing frames.
* `DumpFrame` - is a frame containing a grid which automatically resizes and can display
                arbitrary data.
* `DumpFileFrame` - is a subclass of DumpFrame which displays data from a file.
"""

import wx
import wx.grid as gridlib

import dump


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

    # Extra menu entries as a list of tuples:
    #   (menu item title, function to call, selection state)
    #   selection state: False for non-check function
    #                    True for selected item
    #   function has the args (grid, dump, chosen)
    #   chosen is the selection state when selected, or None to read state
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

    # Whether the grid lines should be shown between cells
    has_grid = False

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

                rowbytevalues = [ord(c) for c in rowdata]
                rowtext = self.dump.format_chars(rowbytevalues)
                rowannotation = self.dump.format_annotation(row)

            if len(self.row_cache) > self.row_cache_limit:
                # Reset the cache so that we don't accumulate forever
                #print("Clear row cache")
                self.row_cache = {}

            self.row_cache[row] = (rowvalues, rowtext, rowannotation)

        return self.row_cache[row]


class DumpStatusBar(wx.StatusBar):

    def __init__(self, parent):
        super(DumpStatusBar, self).__init__(parent, -1)
        # Nothing special to do here?


class DumpGrid(gridlib.Grid):

    def __init__(self, parent, data, config=None):
        super(DumpGrid, self).__init__(parent, -1, style=wx.VSCROLL)

        self.config = config or WxDumpConfig()
        self.parent = parent
        self.data = data
        self.menu_items = []
        self.dump = dump.DumpBase()
        self.dump.data = data
        for key, value in self.config.dump_params.items():
            if getattr(self.dump, key, Ellipsis) is Ellipsis:
                raise AttributeError("Dump parameter '{}' is not recognised".format(key))
            setattr(self.dump, key, value)

        self.table = DumpTable(self.dump, self.data, self.config)
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

        # Build up the menu we'll use
        self.menu = wx.Menu()

        if self.config.has_width_1:
            self.item_bytes = self.menu.Append(-1, "Bytes", kind=wx.ITEM_CHECK)
            self.Bind(wx.EVT_MENU, lambda event: self.SetDumpWidth(1), self.item_bytes)
        else:
            self.item_bytes = None

        if self.config.has_width_2:
            self.item_halfwords = self.menu.Append(-1, "Half words", kind=wx.ITEM_CHECK)
            self.Bind(wx.EVT_MENU, lambda event: self.SetDumpWidth(2), self.item_halfwords)
        else:
            self.item_halfwords = None

        if self.config.has_width_4:
            self.item_words = self.menu.Append(-1, "Words", kind=wx.ITEM_CHECK)
            self.Bind(wx.EVT_MENU, lambda event: self.SetDumpWidth(4), self.item_words)
        else:
            self.item_words = None

        self.add_menu_extra(self.menu)

        self.Bind(gridlib.EVT_GRID_CELL_RIGHT_CLICK, self.on_popup_menu)

    def add_menu_extra(self, menu):
        if self.config.menu_extra:
            menu.AppendSeparator()
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

        self.table = DumpTable(self.dump, self.data, config=self.config)
        self.SetTable(self.table, True)
        self.resize()
        self.parent.resize()

    def SetDumpColumns(self, columns):
        self.dump.columns = columns

        self.table = DumpTable(self.dump, self.data, config=self.config)
        self.SetTable(self.table, True)
        self.resize()
        self.parent.resize()

    def resize(self):
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
        mouse_over = None
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
        (width, height) = self.grid.GetBestSize()
        limit_height = min(height, self.config.frame_max_height)
        self.SetMaxClientSize((width, height))

        self.SetClientSize(width, limit_height)

        (width, height) = self.grid.GetMinSize()
        self.SetMinClientSize(wx.Size(width, height + self.statusbar_height))

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
