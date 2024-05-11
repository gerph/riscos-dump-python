# RISC OS hex dump in Python

## Introduction

The modules in this repository provide a means by which a simple hexadecimal dump
may be provided for data, in the same style as that used by the RISC OS `*Dump`
or `*Memory` commands. The code was originally written for these commands (and the
tracing code) in RISC OS Pyromaniac. It has been extracted to a separate module
as it may be more generally useful.


## Installation

The tool for dumping can be installed manually using this repository
(see 'Usage' below) or through PyPI. To install, use:

    pip3 install riscos_dump


## Usage

Once installed, the tool can be invoked as `riscos-dump`. For example:

    riscos-dump examples/hello_world,ffc

There are two optional parameters:

* `<fileoffset>`: A hexadecimal offset into the file to start from
* `<baseaddr>`: Base address to display content from (defaults to 0 unless this is an Absolute file)

The following switches are supported:

* `--row-size`: Number of bytes listed within a row
* `--words`: Display as words, rather than bytes


## Package contents

The package `riscos_dump` contains all the classes used by the tool.

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

## Example code

The file `simple_dump.py` is a very simple dump tool which just displays a
hexadecimal dump from a file.

The file `wxdumper.py` is a simple application which displays the contents of
a file within a window. It is merely an example to show how the `wxdump.py`
classes can be used.

## Examples

Example files are supplied in the `examples` directory to demonstrate the disassembly:

* `hello_world` utility file (suffixed by `,ffc`) is a test from the RISC OS Pyromaniac project, which verifies the behaviour of the SWI `OS_Write0`.

For example, displaying the content of the `hello_word` binary as bytes:

```
charles@laputa ~/riscos-dump-python $ riscos-dump examples/hello_world,ffc
Offset   :   0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  : Text
       0 :  1C 00 8F E2 02 00 00 EF 20 10 8F E2 01 00 50 E1  : ........ .....P.
      10 :  01 00 00 1A 03 00 00 EF 0E F0 A0 E1 0C 00 8F E2  : ................
      20 :  2B 00 00 EF 48 65 6C 6C 6F 20 77 6F 72 6C 64 00  : +...Hello world.
      30 :  01 00 00 00 52 30 20 6F 6E 20 72 65 74 75 72 6E  : ....R0 on return
      40 :  20 66 72 6F 6D 20 4F 53 5F 57 72 69 74 65 30 20  :  from OS_Write0 
      50 :  77 61 73 20 6E 6F 74 20 63 6F 72 72 65 63 74 6C  : was not correctl
      60 :  79 20 73 65 74 20 74 6F 20 74 68 65 20 74 65 72  : y set to the ter
      70 :  6D 69 6E 61 74 6F 72 00                          : minator.
```

Similarly, to display as words (32bit values):

```
charles@laputa ~/riscos-dump-python $ riscos-dump --words examples/hello_world,ffc
Offset   :         0        4        8        C  : Text
       0 :  E28F001C EF000002 E28F1020 E1500001  : ........ .....P.
      10 :  1A000001 EF000003 E1A0F00E E28F000C  : ................
      20 :  EF00002B 6C6C6548 6F77206F 00646C72  : +...Hello world.
      30 :  00000001 6F203052 6572206E 6E727574  : ....R0 on return
      40 :  6F726620 534F206D 6972575F 20306574  :  from OS_Write0 
      50 :  20736177 20746F6E 72726F63 6C746365  : was not correctl
      60 :  65732079 6F742074 65687420 72657420  : y set to the ter
      70 :  616E696D 00726F74                    : minator.
```

