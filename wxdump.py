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


class DumpTable(gridlib.GridTableBase):
    colours = {
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
    dark_colours = {
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

    def __init__(self, dump, data, dark_colours=True):

        self.dump = dump
        self.data = data
        super(DumpTable, self).__init__()

        # Attributes applying to bytes
        self.attributes = {}
        colours = self.dark_colours if dark_colours else self.colours
        for (name, cols) in colours.items():
            attr = gridlib.GridCellAttr()
            attr.SetBackgroundColour(cols[0])
            attr.SetTextColour(cols[1])
            self.attributes[name] = attr

        self.align_right = (wx.ALIGN_RIGHT, wx.ALIGN_CENTER)
        self.align_left = (wx.ALIGN_LEFT, wx.ALIGN_CENTER)

        self.headings = self.dump.data_headings()
        self.column_alignment = []

        # We keep a cache of the row data we've read from the Dump object, but discard once
        # we reache this limit.
        self.cache_limit = 400
        self.cache_rows = {}

    def update_content(self):
        self.headings = self.dump.data_headings()
        self.column_alignment = [self.align_right] * self.dump.columns
        self.column_alignment.append(self.align_left)

    def GetNumberRows(self):
        rowsize = self.dump.columns * self.dump.width
        return int((len(self.data) + rowsize - 1) / rowsize)

    def GetNumberCols(self):
        columns = self.dump.columns + 1
        if self.dump.annotation_func:
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
        if col == self.dump.columns:
            return self.dump.text_label
        if col == self.dump.columns + 1:
            return self.dump.annotation_label
        return self.headings[col]

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
                    if value < 32 or value == 127:
                        attr = self.attributes['control']
                    elif (64 < value < 91) or (96 < value < 122):
                        attr = self.attributes['alpha']
                    elif (48 < value < 58):
                        attr = self.attributes['number']
                    elif value < 128:
                        attr = self.attributes['plain']
                    else:
                        attr = self.attributes['topbit']
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
        if row not in self.cache_rows:

            rowdata = self.dump.row_data(row)
            if not rowdata:
                # No data, so these cells are empty
                rowvalues = [None] * self.dump.columns
                rowtext = ''
                rowannotation = ''
            else:

                rowvalues = self.dump.row_values(row)
                if len(rowvalues) < self.dump.columns:
                    rowvalues += [None] * (self.dump.columns - len(rowvalues))

                rowbytevalues = [ord(c) for c in rowdata]
                rowtext = self.dump.format_chars(rowbytevalues)
                rowannotation = self.dump.format_annotation(row)

            if len(self.cache_rows) > self.cache_limit:
                # Reset the cache so that we don't accumulate forever
                #print("Clear row cache")
                self.cache_rows = {}

            self.cache_rows[row] = (rowvalues, rowtext, rowannotation)

        return self.cache_rows[row]


class DumpStatusBar(wx.StatusBar):

    def __init__(self, parent):
        super(DumpStatusBar, self).__init__(parent, -1)
        # Nothing special to do here?


class DumpGrid(gridlib.Grid):

    def __init__(self, parent, data, dump_params={},
                 mouse_over=None):
        super(DumpGrid, self).__init__(parent, -1, style=wx.VSCROLL)

        self.parent = parent
        self.data = data
        self.dump = dump.DumpBase()
        self.dump.data = data
        for key, value in dump_params.items():
            if getattr(self.dump, key, Ellipsis) is Ellipsis:
                raise AttributeError("Dump parameter '{}' is not recognised".format(key))
            setattr(self.dump, key, value)

        self.row_annotation_size = 24

        self.table = DumpTable(self.dump, self.data)
        self.SetTable(self.table, True)

        self.cellfont = wx.Font(12, wx.TELETYPE, wx.NORMAL, wx.NORMAL)
        self.SetDefaultCellFont(self.cellfont)
        self.SetLabelFont(wx.Font(12, wx.TELETYPE, wx.NORMAL, wx.FONTWEIGHT_BOLD))

        self.EnableEditing(False)
        self.EnableDragRowSize(False)
        self.EnableDragColSize(False)
        self.EnableGridLines(False)
        self.SetRowLabelAlignment(wx.ALIGN_RIGHT, wx.ALIGN_CENTER)

        self.cellsize = (16 * 2, 16)
        self.labelsize = (16 * 8, 16)
        self.textsize = (16 * 16, 16)
        self.annotationsize = (24 * 16, 16)
        self.min_width = 16
        self.min_height = 16
        self.resize()

        self.mouse_over = mouse_over
        self.last_mouse_over = None
        if self.mouse_over:
            grid_window = self.GetGridWindow()
            grid_window.Bind(wx.EVT_MOTION, self.on_mouse_over)
            grid_window.Bind(wx.EVT_LEAVE_WINDOW, self.on_mouse_out)

        # Build up the menu we'll use
        self.menu = wx.Menu()

        self.item_bytes = self.menu.Append(-1, "Bytes", kind=wx.ITEM_CHECK)
        self.Bind(wx.EVT_MENU, lambda event: self.SetDumpwidth(1), self.item_bytes)

        self.item_words = self.menu.Append(-1, "Words", kind=wx.ITEM_CHECK)
        self.Bind(wx.EVT_MENU, lambda event: self.SetDumpwidth(4), self.item_words)

        self.Bind(gridlib.EVT_GRID_CELL_RIGHT_CLICK, self.on_popup_menu)

    def on_popup_menu(self, event):
        self.item_bytes.Check(self.dump.width == 1)
        self.item_words.Check(self.dump.width == 4)
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
            self.mouse_over(offset)

    def on_mouse_out(self, event):
        self.last_mouse_over = None
        self.mouse_over(None)

    def SetDumpWidth(self, width):
        self.dump.columns = int(self.dump.width * self.dump.columns / width)
        self.dump.width = width

        self.table = DumpTable(self.dump, self.data)
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
        self.annotationsize = dc.GetTextExtent('M' * (self.row_annotation_size + 1))
        # FIXME: This is wrong, but it's about the right sort of size
        self.scrollbarsize = dc.GetTextExtent('M' * 2)[0]

        # Set the column widths
        colsizes = []
        for col in range(self.dump.columns):
            colsizes.append(self.cellsize[0])
        colsizes.append(self.textsize[0])
        if self.dump.annotation_func:
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
    good_height = 600

    def __init__(self, title="Hex Dumper", data=b'', dump_params={},
                 cellinfo=None):
        self.data = data
        super(DumpFrame, self).__init__(None, -1, title=title)

        data = self.GetDumpData()

        self.cellinfo = cellinfo

        self.statusbar = None
        self.statusbar_height = 0
        mouse_over = None
        if self.cellinfo:
            self.statusbar = DumpStatusBar(self)
            self.SetStatusBar(self.statusbar)
            mouse_over = self.update_statusbar
            self.statusbar_height = self.statusbar.GetSize()[1]

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.grid = DumpGrid(self, data, dump_params=dump_params,
                             mouse_over=mouse_over)
        sizer.Add(self.grid)
        self.SetSizer(sizer)

        self.resize()

    def resize(self):
        (width, height) = self.grid.GetBestSize()
        limit_height = min(height, self.good_height)
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
            self.statusbar.SetStatusText(self.cellinfo(offset))

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
