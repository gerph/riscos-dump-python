"""
The interface of a dump grid, which every toolkit's grid implements.

A dump grid is the widget that shows a `Dump` model. The callbacks in the configuration
(`menu_format` and `menu_extra` entries, called as `func(grid, dump, chosen)`) are written
against this interface, so they can be written once and used with any toolkit.

The operations that need the toolkit are abstract. The read-only access to the model is
concrete, and works through the grid's `dump` attribute, which holds the `DumpBase`.
"""


class DumpGridBase(object):
    """
    Base class for a toolkit's dump grid.

    (This is not an abstract base class from `abc`, because the toolkits' own widget classes
    have their own metaclasses; the abstract methods raise `NotImplementedError` instead.)
    """

    # The model being shown (a DumpBase); set by the implementation
    dump = None

    # Operations the toolkit must provide

    def set_data(self, data):
        """
        Replace the data being shown, and redraw.

        @param data:    The bytes to show
        """
        raise NotImplementedError("set_data not implemented")

    def refresh(self):
        """
        Redraw the grid from the model.
        """
        raise NotImplementedError("refresh not implemented")

    def visible_range(self):
        """
        The cells which are visible.

        @return: Tuple of (first column, first row, last column, last row)
        """
        raise NotImplementedError("visible_range not implemented")

    def scroll_to_row(self, row):
        """
        Scroll the grid so that a row is at the top.

        @param row: The row number
        """
        raise NotImplementedError("scroll_to_row not implemented")

    def set_width(self, width):
        """
        Change the width in bytes of each value shown (1, 2 or 4), keeping the number of bytes
        shown on each row the same, and rebuild the grid.
        """
        raise NotImplementedError("set_width not implemented")

    def set_columns(self, columns):
        """
        Change the number of values shown on each row, and rebuild the grid.
        """
        raise NotImplementedError("set_columns not implemented")

    def set_annotations(self, enabled):
        """
        Choose whether the annotation column is shown.

        This takes effect when the grid is next rebuilt by `set_width` or `set_columns`.
        """
        self.dump.annotations = bool(enabled)

    # Read-only access to the model

    def annotations_enabled(self):
        return self.dump.annotations

    def width(self):
        return self.dump.width

    def columns(self):
        return self.dump.columns

    def data(self):
        return self.dump.data

    def row_to_offset(self, row):
        return self.dump.row_to_offset(row)

    def offset_to_row(self, offset):
        return self.dump.offset_to_row(offset)

    def row_data(self, row):
        return self.dump.row_data(row)
