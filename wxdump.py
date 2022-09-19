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

    def __init__(self, dump, data):
        self.dump = dump
        self.data = data
        super(DumpTable, self).__init__()

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
        return self.dump.columns + 1

    def IsEmptyCell(self, row, col):
        if col == self.dump.columns:
            # The text column is always valid
            return False
        (rowvalues, rowtext) = self.setup_row(row)
        if not rowvalues:
            return True
        return rowvalues[col] is None

    def GetColLabelValue(self, col):
        if col == self.dump.columns:
            return self.dump.text_label
        return self.headings[col]

    def GetRowLabelValue(self, row):
        return self.dump.format_address(self.dump.row_to_offset(row))

    def GetCellAlignment(self, row, col):
        return self.column_alignment[col]

    def GetValue(self, row, col):
        (rowvalues, rowtext) = self.setup_row(row)
        if not rowvalues:
            return '<invalid>'

        if col < self.dump.columns:
            width = self.dump.width
            value = rowvalues[col]
            if value is None:
                return None
            if width == 1:
                return '{:02x}'.format(value)
            elif width == 4:
                return '{:08x}'.format(value)
            elif width == 2:
                return '{:04x}'.format(value)
            return value
        else:
            return rowtext

    def setup_row(self, row):
        if row not in self.cache_rows:

            rowdata = self.dump.row_data(row)
            if not rowdata:
                # No data, so these cells are empty
                rowvalues = [None] * self.dump.columns
                rowtext = ''
            else:

                rowvalues = self.dump.row_values(row)
                if len(rowvalues) < self.dump.columns:
                    rowvalues += [None] * (self.dump.columns - len(rowvalues))

                rowbytevalues = [ord(c) for c in rowdata]
                rowtext = self.dump.format_chars(rowbytevalues)

            if len(self.cache_rows) > self.cache_limit:
                # Reset the cache so that we don't accumulate forever
                #print("Clear row cache")
                self.cache_rows = {}

            self.cache_rows[row] = (rowvalues, rowtext)

        return self.cache_rows[row]


class DumpGrid(gridlib.Grid):

    def __init__(self, parent, data, dump_params={}):
        super(DumpGrid, self).__init__(parent, -1, style=wx.VSCROLL)

        self.data = data
        self.dump = dump.DumpBase()
        self.dump.data = data
        for key, value in dump_params.items():
            if getattr(self.dump, key, Ellipsis) is Ellipsis:
                raise AttributeError("Dump parameter '{}' is not recognised".format(key))
            setattr(self.dump, key, value)

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

        self.BeginBatch()

        dc = wx.ScreenDC()
        dc.SetFont(self.cellfont)
        cellsize = dc.GetTextExtent('0' * (self.dump.width * 2 + 1))
        for col in range(self.dump.columns):
            self.SetColSize(col, cellsize[0])
        self.SetColLabelSize(cellsize[1] * 1.5)

        textsize = dc.GetTextExtent('M' * (self.dump.width * self.dump.columns + 3))
        self.SetColSize(self.dump.columns, textsize[0])
        self.min_height = textsize[1] * 1.5

        labelsize = dc.GetTextExtent('M' * 9)
        self.SetRowLabelSize(labelsize[0])
        self.min_width = labelsize[0]

        self.EndBatch()
        self.AdjustScrollbars()

        (width, height) = self.GetBestSize()
        limit_height = min(height, 600)
        dx = wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X)

        self.SetMaxSize((width + dx, height))

    def GetMinSize(self):
        return wx.Size(self.min_width, self.min_height)

class DumpFrame(wx.Frame):
    """
    A Frame which can display arbitrary data.
    """
    good_height = 600

    def __init__(self, title="Hex Dumper", data=b'', dump_params={}):
        self.data = data
        super(DumpFrame, self).__init__(None, -1, title=title)

        data = self.GetDumpData()

        sizer = wx.BoxSizer(wx.VERTICAL)
        grid = DumpGrid(self, data, dump_params=dump_params)
        sizer.Add(grid)
        self.SetSizer(sizer)

        (width, height) = self.GetBestSize()
        limit_height = min(height, self.good_height)
        self.SetMaxSize((width, height))

        self.SetSize(width, limit_height)

        (width, height) = grid.GetMinSize()
        self.SetMinClientSize(wx.Size(width, height))

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
