"""
Toolkit-independent configuration for the dump displays.

The configuration describes how a dump is presented: the colours of each kind of cell, the
menu entries, which of the width and menu choices are offered, and so on. Colours are
`(red, green, blue)` tuples of 0-255 values; each toolkit converts them to its own colour type.

Each entry of `colours` is `(background, text)`; the text colour is None where it is not used
(the grid lines and the cursor). `DumpConfig` is dark text on a light background, and
`DumpConfigDark` is light text on a dark one.
"""

# Colours, with the names they were originally given (by the wxPython colour database)
WHITE = (255, 255, 255)         # white
BLACK = (0, 0, 0)               # black
GREY = (128, 128, 128)          # grey
BLUE = (0, 0, 255)              # blue
SLATE_BLUE = (106, 90, 205)     # slate blue
FOREST_GREEN = (34, 139, 34)    # forest green
SKY_BLUE = (135, 206, 235)      # sky blue
GREEN = (0, 128, 0)             # green


class DumpConfig(object):
    colours = {
            # Grid lines and the cursor
            'grid': (GREY, None),
            'cursor': (BLUE, None),

            # Invalid cells
            'invalid': (WHITE, BLACK),

            # Attributes for the main cells
            'plain': (WHITE, BLACK),
            'alpha': (WHITE, BLACK),
            'number': (WHITE, BLACK),
            'control': (WHITE, SLATE_BLUE),
            'topbit': (WHITE, FOREST_GREEN),

            # Attributes applying to words or halfwords
            'word': (WHITE, BLACK),
            'halfword': (WHITE, BLACK),

            # Attributes for the text column
            'text': (WHITE, BLACK),

            # Attributes for the annotation column
            'annotation': (WHITE, BLACK),
        }

    # Parameters to pass on to the Dump object
    dump_params = {}

    # Number of characters in the row annotations
    row_annotation_size = 24

    # Menu entries as a list of tuples:
    #   (menu item title, function to call, selection state)
    #   selection state: False for non-check function
    #                    True for selected item
    #   function has the args (grid, dump, chosen)
    #   chosen is the selection state when selected, or None to read state
    # `menu_format`: adds entries that change the format of the display (eg 'show disassembly')
    # `menu_extra`: adds entries that operate on the display
    menu_format = []
    menu_extra = []

    # How many rows we will cache at a time
    row_cache_limit = 400

    # How high the default size of the frame should be
    frame_max_height = 600

    # Status bar enable
    frame_statusbar = False

    # Which of the data width choices are available:
    has_width_1 = True
    has_width_2 = True
    has_width_4 = True

    # Which of the menu operations are available:
    has_goto_address = True
    has_find_string = True

    # Whether the grid lines should be shown between cells
    has_grid = False

    # Whether we show the save data menu option
    has_save_data = True
    default_savedata_filename = 'Dump.bin'

    byte_colour = [0] * 256
    for b in range(256):
        if b < 32 or b == 127:
            colour_name = 'control'
        elif (64 < b < 91) or (96 < b < 122):
            colour_name = 'alpha'
        elif (48 < b < 58):
            colour_name = 'number'
        elif b < 128:
            colour_name = 'plain'
        else:
            colour_name = 'topbit'

        byte_colour[b] = colour_name

    def cell_info(self, offset):
        """
        Information about a given offset, used by the Frame code.

        @param offset:  The offset to get information from

        @return:    Status bar text for this offset, or None
        """
        return None

    def mouse_over(self, offset):
        """
        Called when the mouse is over a new cell.

        @param offset:  Data offset, or None if the pointer has moved out of the grid.
        """
        pass


class DumpConfigDark(DumpConfig):
    colours = {
            # Grid lines and the cursor
            'grid': (GREY, None),
            'cursor': (BLUE, None),

            # Invalid cells
            'invalid': (BLACK, WHITE),

            # Attributes for the main cells
            'plain': (BLACK, WHITE),
            'alpha': (BLACK, WHITE),
            'number': (BLACK, WHITE),
            'control': (BLACK, SKY_BLUE),
            'topbit': (BLACK, GREEN),

            # Attributes applying to words or halfwords
            'word': (BLACK, WHITE),
            'halfword': (BLACK, WHITE),

            # Attributes for the text column
            'text': (BLACK, WHITE),

            # Attributes for the annotation column
            'annotation': (BLACK, WHITE),
        }
