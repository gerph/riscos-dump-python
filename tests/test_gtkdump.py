#!/usr/bin/env python3
"""
Tests for the GTK dump grid. They need PyGObject and an X display, and report that they were not
run (and pass) if either is missing.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, Gtk
    if Gdk.Display.get_default() is None:
        raise ImportError("no display")
    import riscos_dump.gtkdump as gtkdump
    import riscos_dump.dumpconfig as dumpconfig
    import riscos_dump.dumpgrid as dumpgrid
except Exception as exc:
    gtkdump = None
    reason = str(exc)


@unittest.skipIf(gtkdump is None, "GTK is not available")
class TestGtkDump(unittest.TestCase):

    def make(self, data=bytes(range(256)) * 4, config=None):
        frame = gtkdump.DumpFrame('Test', data=data, config=config or dumpconfig.DumpConfig())
        frame.show_all()
        return frame

    def test_it_is_a_dump_grid(self):
        self.assertIsInstance(self.make().grid, dumpgrid.DumpGridBase)

    def test_rows_and_columns(self):
        grid = self.make().grid
        self.assertEqual((grid.width(), grid.columns(), grid.dump.rows()), (1, 16, 64))

    def test_set_width_keeps_the_bytes_in_a_row(self):
        grid = self.make().grid
        grid.set_width(4)
        self.assertEqual((grid.width(), grid.columns()), (4, 4))
        grid.set_columns(2)
        self.assertEqual(grid.dump.rows(), 128)

    def test_annotations(self):
        grid = self.make().grid
        (positions, narrow) = grid.column_positions()
        grid.set_annotations(True)
        grid.set_columns(16)
        (positions, wide) = grid.column_positions()
        self.assertGreater(wide, narrow)

    def test_set_data_replaces_the_data_and_the_cache(self):
        grid = self.make().grid
        grid.row_cells(0)
        grid.set_data(b'abc' * 20)
        self.assertEqual(grid.data(), b'abc' * 20)
        self.assertEqual(grid.row_cells(0)[0][0], ord('a'))
        self.assertEqual(grid.dump.rows(), 4)

    def test_goto_and_find(self):
        grid = self.make(data=b'hello world, hello again').grid
        grid.goto_address(5)
        self.assertEqual(grid.get_address(), 5)
        self.assertEqual(grid.find_string('hello'), 13)
        self.assertIsNone(grid.find_string('nothing'))

    def test_offsets_outside_the_data_are_none(self):
        grid = self.make(data=b'abc').grid
        self.assertEqual(grid.offset_of(0, 2), 2)
        self.assertIsNone(grid.offset_of(0, 3))
        self.assertIsNone(grid.offset_of(0, None))

    def test_config_menu_items_are_called_with_the_grid(self):
        calls = []
        config = dumpconfig.DumpConfig()
        config.menu_extra = [("Refresh", lambda grid, dump, chosen=False: calls.append((grid, dump, chosen)))]
        grid = self.make(config=config).grid
        refresh = [item for item in grid.menu_items if item[1] == 'Refresh'][0]
        refresh[2](grid, grid.dump, chosen=True)
        self.assertEqual(calls, [(grid, grid.dump, True)])

    def test_status_bar_shows_the_cell_information(self):
        config = dumpconfig.DumpConfig()
        config.frame_statusbar = True
        config.cellinfo = lambda offset: 'offset {}'.format(offset)
        frame = self.make(config=config)
        config.mouse_over(7)
        self.assertEqual(frame.statusbar.get_message_area().get_children()[0].get_text(), 'offset 7')
        config.mouse_over(None)
        self.assertEqual(frame.statusbar.get_message_area().get_children()[0].get_text(), '')


if __name__ == '__main__':
    unittest.main()
