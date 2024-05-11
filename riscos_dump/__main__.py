#!/usr/bin/env python
"""
Command line tool for dumping files.
"""

import argparse
import errno
import sys

import riscos_dump.dump as dump


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename',
                        help="Filename of binary to dump")
    parser.add_argument('--row-size', action='store', default=16, type=int,
                        help="Number of bytes in a row")
    parser.add_argument('--words', action='store_true', default=False,
                        help="Dump in 32bit words (defaults to bytes)")
    parser.add_argument('fileoffset', nargs='?', default=0, type=lambda x: int(x, 16),
                        help="File offset to dump from")
    parser.add_argument('baseaddr', nargs='?', default=None, type=lambda x: int(x, 16),
                        help="Base address for the file contents")

    options = parser.parse_args()

    row_size = options.row_size
    filename = options.filename

    dumper = dump.Dump()
    if options.words:
        dumper.width = 4
        dumper.columns = int(row_size / dumper.width)

    # Work out the address that the file starts at
    baseaddr = options.baseaddr
    if baseaddr is None:
        baseaddr = 0
        if filename.endswith(',ff8'):
            baseaddr = 0x8000

    # Calculate the starting address that we will display from
    dumper.address_base = baseaddr + options.fileoffset

    try:
        with open(filename, 'rb') as fh:

            filedata = dump.FileDataSource(fh)
            filedata.base_offset = options.fileoffset

            dumper.show(filedata)

    except IOError as exc:
        if exc.errno == errno.EISDIR:
            sys.exit("'%s' is a directory" % (options.filename,))
        if exc.errno == errno.ENOENT:
            sys.exit("'%s' not found" % (options.filename,))
        if exc.errno == errno.EACCES:
            sys.exit("'%s' is not accessible" % (options.filename,))
        if exc.errno == errno.EPIPE:
            # Broken pipe - probably means that they were more-ing the file,
            # and cancelled, or maybe piped through head or similar.
            # We don't want to report anything else, but just fail.
            # Close the stdout and stderr explicitly, ignoring errors, so
            # that the implicit close on exit doesn't report an error and
            # fail with 'close failed in file object destructor'.
            try:
                sys.stdout.close()
            except Exception:
                pass
            try:
                sys.stderr.close()
            except Exception:
                pass
            sys.exit(1)
        raise

    except KeyboardInterrupt:
        sys.exit("Interrupted")


if __name__ == '__main__':
    main()
