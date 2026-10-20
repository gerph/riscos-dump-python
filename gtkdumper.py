#!/usr/bin/env python
"""
Hex dump display of files, as a GTK application.

This is really just a simple harness to test that the dump library works with GTK.

    gtkdumper.py [--dark] [--words] <file>
"""

import argparse

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import riscos_dump.dump as dump
import riscos_dump.dumpconfig as dumpconfig
import riscos_dump.gtkdump as gtkdump


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', help="File to display")
    parser.add_argument('--dark', action='store_true', default=False, help="Use the dark colours")
    parser.add_argument('--words', action='store_true', default=False, help="Show 32bit words")
    options = parser.parse_args()

    with open(options.filename, 'rb') as fh:
        data = fh.read()

    config = dumpconfig.DumpConfigDark() if options.dark else dumpconfig.DumpConfig()
    config.default_savedata_filename = options.filename.split('/')[-1]
    if options.words:
        config.dump_params = {'width': 4, 'columns': 4}

    frame = gtkdump.DumpFrame(options.filename, data=data, config=config)
    frame.connect("destroy", Gtk.main_quit)
    frame.show_all()
    Gtk.main()


if __name__ == '__main__':
    main()
