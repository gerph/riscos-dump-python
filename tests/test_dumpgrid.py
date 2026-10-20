#!/usr/bin/env python3
"""
Tests for the toolkit-independent dump configuration and grid interface (no toolkit needed).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from riscos_dump import dump
from riscos_dump import dumpconfig
from riscos_dump import dumpgrid


class RecordingGrid(dumpgrid.DumpGridBase):
    """A grid with no toolkit, which records what it is asked to do."""

    def __init__(self, data=b''):
        self.dump = dump.DumpBase()
        self.dump.data = data
        self.log = []

    def set_data(self, data):
        self.dump.data = data
        self.log.append(('set_data', len(data)))

    def refresh(self):
        self.log.append(('refresh',))

    def visible_range(self):
        return (0, 2, 3, 5)

    def scroll_to_row(self, row):
        self.log.append(('scroll_to_row', row))

    def set_width(self, width):
        self.dump.columns = int(self.dump.width * self.dump.columns / width)
        self.dump.width = width
        self.log.append(('set_width', width))

    def set_columns(self, columns):
        self.dump.columns = columns
        self.log.append(('set_columns', columns))


class TestConfig(unittest.TestCase):

    def triples(self, config):
        values = []
        for (background, text) in config.colours.values():
            for colour in (background, text):
                if colour is not None:
                    values.append(colour)
        return values

    def test_colours_are_rgb_triples(self):
        for config in (dumpconfig.DumpConfig, dumpconfig.DumpConfigDark):
            for colour in self.triples(config):
                self.assertEqual(len(colour), 3)
                for component in colour:
                    self.assertTrue(0 <= component <= 255)

    def test_every_byte_has_a_colour_entry(self):
        for config in (dumpconfig.DumpConfig, dumpconfig.DumpConfigDark):
            for name in config.byte_colour:
                self.assertIn(name, config.colours)

    def test_byte_classes(self):
        colour = dumpconfig.DumpConfig.byte_colour
        self.assertEqual(colour[0], 'control')
        self.assertEqual(colour[ord('A')], 'alpha')
        self.assertEqual(colour[ord('5')], 'number')
        self.assertEqual(colour[ord(' ')], 'plain')
        self.assertEqual(colour[0xff], 'topbit')

    def test_light_and_dark_are_opposites(self):
        light = dumpconfig.DumpConfig.colours['plain']
        dark = dumpconfig.DumpConfigDark.colours['plain']
        self.assertEqual(light, (dumpconfig.WHITE, dumpconfig.BLACK))
        self.assertEqual(dark, (dumpconfig.BLACK, dumpconfig.WHITE))


class TestGridBase(unittest.TestCase):

    def test_toolkit_operations_are_abstract(self):
        grid = dumpgrid.DumpGridBase()
        for call in (lambda: grid.set_data(b''), grid.refresh, grid.visible_range,
                     lambda: grid.scroll_to_row(1), lambda: grid.set_width(1),
                     lambda: grid.set_columns(1)):
            with self.assertRaises(NotImplementedError):
                call()

    def test_model_access(self):
        grid = RecordingGrid(bytes(range(64)))
        grid.dump.columns = 16
        self.assertEqual(grid.width(), 1)
        self.assertEqual(grid.columns(), 16)
        self.assertEqual(grid.data(), bytes(range(64)))
        self.assertEqual(grid.row_to_offset(2), 32)
        self.assertEqual(grid.offset_to_row(33), 2)
        self.assertEqual(grid.row_data(1), bytes(range(16, 32)))

    def test_annotations(self):
        grid = RecordingGrid()
        self.assertFalse(grid.annotations_enabled())
        grid.set_annotations(True)
        self.assertTrue(grid.annotations_enabled())
        self.assertTrue(grid.dump.annotations)

    def test_a_callback_can_be_written_against_the_interface(self):
        # The shape of a "toggle disassembly" callback
        grid = RecordingGrid(bytes(range(256)))
        grid.dump.columns = 16
        top_offset = grid.row_to_offset(grid.visible_range()[1])
        grid.set_annotations(True)
        grid.set_width(4)
        grid.set_columns(1)
        grid.scroll_to_row(grid.offset_to_row(top_offset))
        self.assertEqual(grid.columns(), 1)
        self.assertEqual(grid.width(), 4)
        self.assertEqual(grid.log[-1], ('scroll_to_row', 2 * 16 // 4))


if __name__ == '__main__':
    unittest.main()
