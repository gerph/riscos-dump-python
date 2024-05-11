#!/usr/bin/env python
"""
Command line tool for dumping files.
"""

import argparse
import sys

import riscos_dump.dump


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('binary',
                        help="Binary file to dump")
    parser.add_argument('--row-size', action='store', default=16, type=int,
                        help="Number of bytes in a row")
    parser.add_argument('--words', action='store_true', default=False,
                        help="Dump in 32bit words (defaults to bytes)")

    options = parser.parse_args()

    row_size = options.row_size
    filename = options.binary

    dumper = dump.Dump()
    if options.words:
        dumper.width = 4
        dumper.columns = int(row_size / dumper.width)

    with open(filename, 'rb') as fh:

        filedata = dump.FileDataSource(fh)
        dumper.show(filedata)


if __name__ == '__main__':
    main()
