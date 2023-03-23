"""
Class for displaying information the form of a byte or word dump.

It is intended that the class be configured for a given use, and then data supplied to it.
It's reasonably flexible for the cases that we want to display.

The class is intended to display dumped data that looks like this:

  Offset :  0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f : Text
       0 : 00 01 08 00 06 04 00 01 50 79 72 6f 00 00 01 02 : ........Pyro....
      10 : 03 04 00 00 00 00 00 00 01 02 03 04             : ............

It can be displayed in widths of 1, 2, 4, and 8 bytes, in little or big endian, with and
without the text area. Offsets are configurable, and the number of columns are changeable.
"""

import io
import struct
import sys


class DumpBase(object):
    """
    Base class which works out all the parameters for the memory dump.

    The base class does nothing with rendering of the data. It merely prepares and
    processes the data so that the rows and columns will be presentable.
    """

    # Class variable which caches format strings for all objects
    format_strings = {}

    def __init__(self):
        self.address_base = 0

        self.columns = 16
        self.width = 1  # Must be 1, 2, 4, 8

        self.address_label = 'Offset'
        self.text_label = 'Text'
        self.annotation_label = 'Notes'
        self.annotation_func = None
        self.annotations = False
        self.text_high = False
        self.text = True
        self.little_endian = True

        self.data = b''

    def data_headings(self):
        headings = []
        maxoffset = self.columns * self.width
        if maxoffset < 16:
            if self.columns == 1:
                headings = ['Value']
            else:
                headings.extend('+{:X}'.format(v) for v in range(0, maxoffset, self.width))

        elif maxoffset == 16:
            headings.extend('{:X}'.format((v + self.address_base) % 16) for v in range(0, maxoffset, self.width))
        else:
            headings.extend('+{:X}'.format(v) for v in range(0, maxoffset, self.width))

        return headings

    def headings(self):
        headings = self.data_headings()
        if self.text:
            headings.append(self.text_label)
        if self.annotations:
            headings.append(self.annotation_label)
        return headings

    def row_to_offset(self, row):
        """
        Convert from a row number to a data offset.
        """
        return self.columns * self.width * row

    def offset_to_row(self, offset):
        """
        Convert from a data offset to a row number.
        """
        return int(offset / (self.columns * self.width))

    def address_to_coords(self, address):
        """
        Convert from a data address to a coordinate pair.

        @param address: address to find

        @return:        tuple of (row, column) or (None, None) if outside range
        """
        offset = address - self.address_base
        rowsize = self.columns * self.width
        if offset < 0 or offset > len(self.data):
            return (None, None)
        return (int(offset / rowsize), offset % rowsize)

    def coords_to_address(self, row, col, bound=False):
        """
        Convert from a coordinate pair to a data address.

        @param row:     Row
        @param col:     Column
        @param bound:   True to bound to the limits, False to return None if invalid

        @return:        address, or None if invalid
        """
        if col > self.columns:
            if bound:
                col = self.columns - 1
            else:
                return None
        if col < 0:
            if bound:
                col = 0
            else:
                return None
        if row < 0:
            if bound:
                row = 0
            else:
                return None

        offset = (row * self.columns * self.width) + (col * self.width)
        if offset > len(self.data):
            if bound:
                offset = max(len(self.data) - 1, 0)
            else:
                return None

        return offset + self.address_base

    def rows(self):
        """
        Return the number of rows present.
        """
        rowsize = self.columns * self.width
        return int((len(self.data) + rowsize - 1) / rowsize)

    def format_address(self, offset):
        return '{:x}'.format(offset + self.address_base)

    def format_chars(self, data):
        if self.text_high:
            valid = lambda c: (c >= 32 and c < 0x7f) or (c >= 0xa0)
        else:
            valid = lambda c: c >= 32 and c < 0x7f
        return ''.join(chr(c) if valid(c) else '.' for c in data)

    def format_annotation(self, row):
        if self.annotations:
            if self.annotation_func:
                offset = self.row_to_offset(row)
                address = offset + self.address_base
                note = self.annotation_func(self, row, offset, address) or ''
            else:
                note = ''
            return note
        return None

    def row_data(self, row):
        """
        Return the data for a given row.
        """
        start = self.row_to_offset(row)
        end = self.row_to_offset(row + 1)
        return bytearray(self.data[start:end])

    def row_values(self, row):
        """
        Return the data for a given row.
        """
        rowdata = self.row_data(row)

        if self.width == 1:
            return [b for b in rowdata]

        if len(rowdata) % self.width != 0:
            rowdata += '\x00' * (self.width - (len(rowdata) % self.width))

        key = (self.width, len(rowdata), self.little_endian)
        format_string = self.format_strings.get(key, None)
        if format_string is None:
            if self.width == 2:
                format_string = 'H'
            elif self.width == 4:
                format_string = 'L'
            elif self.width == 8:
                format_string = 'Q'
            format_string = format_string * int(len(rowdata) / self.width)
            if self.little_endian:
                format_string = '<' + format_string
            else:
                format_string = '>' + format_string
            self.format_strings[key] = format_string

        rowvalues = struct.unpack(format_string, rowdata)
        return rowvalues


class Dump(DumpBase):

    def __init__(self, fh=None):
        super(Dump, self).__init__()
        if fh is None:
            fh = sys.stdout
        self.fh = fh
        self.offset_highlight = None
        self.indent = ''
        self.heading = True
        self.heading_every = 16
        self.heading_breaks = True
        self.zero_pad_offset = False
        self.row_count = 0
        self.pad_data = True
        self.prefix_chars = {}

    def writeln(self, msg):
        self.fh.write(msg + '\n')

    def format_address(self, offset):
        if self.zero_pad_offset:
            return '{:08X}'.format(offset + self.address_base)
        else:
            return '{:8X}'.format(offset + self.address_base)

    def format_row(self, row_count):
        rowdata = self.row_data(row_count)
        if not rowdata:
            return None

        offset = self.row_to_offset(row_count)

        rowbytevalues = rowdata
        rowvalues = self.row_values(row_count)

        rowdesc = ''.join('{}{:0{}X}'.format(self.prefix_chars.get(offset + i * self.width, ' '),
                                             v, self.width * 2) for i, v in enumerate(rowvalues))
        if self.prefix_chars.get(offset + (len(rowvalues) - 1) * self.width, None) == '>':
            rowdesc += '<'
        else:
            rowdesc += ' '
        if rowdesc[0] == '<':
            rowdesc = ' ' + rowdesc[1:]
        if len(rowvalues) < self.columns:
            padding = ((' ' * (self.width * 2)) + ' ') * (self.columns - len(rowvalues))
            if rowdesc[-1] == '<':
                rowdesc += padding[1:]
            else:
                rowdesc += padding

        if self.text:
            rowchars = self.format_chars(rowbytevalues)
            rowtext = ': {}'.format(rowchars)
        else:
            rowtext = ''

        rowtitle = self.format_address(offset)
        rownote = ''
        if self.annotations:
            rownote = " : {}".format(self.format_annotation(row_count))

        return "{}{} :{}{}{}{}{}".format(self.indent, rowtitle,
                                         ' ' if self.pad_data else '',
                                         rowdesc,
                                         ' ' if self.pad_data else '',
                                         rowtext,
                                         rownote)

    def update_prefix_chars(self):
        self.prefix_chars = {}
        if self.offset_highlight is not None:
            self.prefix_chars[self.offset_highlight] = '>'
            self.prefix_chars[self.offset_highlight + self.width] = '<'

    def show(self, data):
        self.data = data

        self.update_prefix_chars()

        self.row_count = 0
        while True:
            line = self.format_row(self.row_count)
            if not line:
                break

            if self.heading:
                if (self.row_count % self.heading_every) == 0:
                    if self.row_count != 0 and self.heading_breaks:
                        self.writeln('')

                    rowtitle = '{:<8}'.format(self.address_label)
                    rowcolumns = ''.join('{:>{}}'.format(heading, self.width * 2 + 1) for heading in self.data_headings())

                    if self.text:
                        rowtext = ' : {}'.format(self.text_label)
                    self.writeln("{}{} :{}{}{}{}".format(self.indent,
                                                         rowtitle,
                                                         ' ' if self.pad_data else '',
                                                         rowcolumns,
                                                         ' ' if self.pad_data else '',
                                                         rowtext))

                    if self.heading_breaks == 2:
                        self.writeln('')

            self.writeln(line)
            self.row_count += 1


class FileDataSource(object):
    search_chunk_size = 1024

    def __init__(self, fh):
        self.fh = fh
        self.offset = -1
        self.base_offset = 0
        self._len = None

    def __len__(self):
        if self._len is None:
            self.fh.seek(0, io.SEEK_END)
            self.offset = -1
            self._len = self.fh.tell() - self.base_offset
            if self._len < 0:
                self._len = 0

        return self._len

    def __getitem__(self, index):
        if isinstance(index, int):
            start = index
            size = 1
        elif isinstance(index, slice):
            start = index.start
            size = index.stop - index.start
            # Ignore the step
        else:
            raise IndexError("Cannot use items of type %s with FileDataSource" % (index.__class__.__name__,))

        if self.offset != start:
            self.fh.seek(start + self.base_offset)
            self.offset = start
        data = self.fh.read(size)
        self.offset += len(data)
        return data

    def __bytes__(self):
        return self[0:len(self)]

    def find(self, s, start=0):
        """
        From a specific point in the file, find a byte string.

        @param s:       Byte string to look for
        @param start:   Offset in the file to search from

        @return:    -1 if not found, or index from the base offset if found
        """

        search_size = max(len(s) + self.search_chunk_size, self.search_chunk_size * 2)
        skip_size = search_size - len(s)

        # We search in chunks within the file, trying to find the string in each chunk.
        # If we don't find the string, we move through the file keeping the window so
        # that we can get the entries without holding the whole file in memory at once.
        self.fh.seek(start + self.base_offset, io.SEEK_SET)
        datastart = start
        data = b''
        while True:
            newdata = self.fh.read(search_size)
            if not newdata:
                # There was no more data, and we're at the end of the file, so we didn't find it.
                return -1
            data += newdata
            index = data.find(s)
            if index != -1:
                # We found it! So we can return the offset
                return datastart + index
            # Not found, so we need to accumulate more
            data = data[skip_size:]
            datastart += skip_size
