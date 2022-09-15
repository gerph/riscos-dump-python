# RISC OS hex dump in Python

## Introduction

The modules in this repository provide a means by which a simple hexadecimal dump
may be provided for data, in the same style as that used by the RISC OS `*Dump`
or `*Memory` commands. The code was originally written for these commands (and the
tracing code) in RISC OS Pyromaniac. It has been extracted to a separate module
as it may be more generally useful.

## Usage

The `dump.py` module provides the implementation of the hexadecimal dumping.
Two classes are provided - `DumpBase` and `Dump`. The `DumpBase` class provides
the basics of decoding and deciding how the data supplied should be presented.
The `Dump` class is derived from `DumpBase` and provides a presentation for a
terminal.

A class `FileDataSource` is provided, which allows indexed access to the content
of a seekable file through a file handle.  This allows the data supplied to the
`DumpBase`/`Dump` objects to be loaded dynamically from disc.

The file `dumper.py` provides a very simple example of the usage of the Dump
objects. For more information on the usage, examine the `dump.py` module.

The file `wxdump.py` uses the `dump.py` module to construct WxPython grids and
frames containing a scrollable window of data. These are limited in their
flexibility at present, but may be extended through subclassing to provide more
functionality.

Two frame implementations exist - `DumpFrame`, which can be supplied data to
display; and `DumpFileFrame`, which will read the data from a file. Both can be
supplied a dictionary of parameters to set on the `DumpBase` object.

The file `wxdumper.py` is a simple application which displays the contents of
a file within a window. It is merely an example to show how the `wxdump.py`
classes can be used.
