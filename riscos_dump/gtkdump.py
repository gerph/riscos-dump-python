"""
GTK classes for dumping hexadecimal information using the Dump object.

* `DumpGrid`: is an embedable widget which shows a dump, and implements `DumpGridBase`.
* `DumpFrame`: is a window containing a grid which automatically sizes itself and can display
               arbitrary data.

These are the GTK 3 counterparts of the classes in `wxdump`, and take the same
configuration (`dumpconfig.DumpConfig`).
"""

import math

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo

import riscos_dump.dump as dump
import riscos_dump.dumpconfig as dumpconfig
import riscos_dump.dumpgrid as dumpgrid


FONT = "Monospace 11"
PADDING = 4


def to_rgba(value):
    """
    Convert a colour from the configuration (an RGB tuple, a name, or None) to a Gdk.RGBA.
    """
    if value is None:
        return None
    if isinstance(value, str):
        rgba = Gdk.RGBA()
        if not rgba.parse(value):
            return None
        return rgba
    return Gdk.RGBA(value[0] / 255.0, value[1] / 255.0, value[2] / 255.0, 1.0)


class DumpGrid(dumpgrid.DumpGridBase, Gtk.ScrolledWindow):
    """
    A scrolling grid which shows a dump: a row label for the address, the data in cells, the data
    as text and, if enabled, an annotation for each row.
    """

    def __init__(self, data, config=None, frame=None):
        super(DumpGrid, self).__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.config = config or dumpconfig.DumpConfig()
        self.frame = frame
        self.menu_items = []

        self.dump = dump.DumpBase()
        self.dump.data = data
        for key, value in self.config.dump_params.items():
            if getattr(self.dump, key, Ellipsis) is Ellipsis:
                raise AttributeError("Dump parameter '{}' is not recognised".format(key))
            setattr(self.dump, key, value)

        self.row_cache = {}
        self.cursor = None
        self.last_mouse_over = None
        self.last_find_string = ''
        self.colours = {}
        for (name, (background, text)) in self.config.colours.items():
            self.colours[name] = (to_rgba(background), to_rgba(text))

        self.canvas = Gtk.DrawingArea()
        self.canvas.set_can_focus(True)
        self.canvas.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK |
                               Gdk.EventMask.LEAVE_NOTIFY_MASK | Gdk.EventMask.KEY_PRESS_MASK)
        self.canvas.connect("draw", self.on_draw)
        self.canvas.connect("button-press-event", self.on_button_press)
        self.canvas.connect("motion-notify-event", self.on_motion)
        self.canvas.connect("leave-notify-event", self.on_leave)
        self.canvas.connect("key-press-event", self.on_key)
        self.add(self.canvas)

        self.font = Pango.FontDescription(FONT)
        layout = self.canvas.create_pango_layout("0")
        layout.set_font_description(self.font)
        (self.char_width, self.char_height) = layout.get_pixel_size()
        self.row_height = self.char_height + 2

        self.build_menu()
        self.update_size()

    # Geometry

    def address_chars(self):
        last = self.dump.format_address(max(len(self.dump.data) - 1, 0)).upper()
        return max(len(last), 4) + 1

    def cell_chars(self):
        return self.dump.width * 2

    def annotation_chars(self):
        return self.config.row_annotation_size

    def column_positions(self):
        """
        The x position and width, in pixels, of the label, each data cell, the text and the
        annotation.
        """
        positions = []
        x = 0
        label_width = self.address_chars() * self.char_width + PADDING * 2
        positions.append((x, label_width))
        x += label_width
        cell_width = self.cell_chars() * self.char_width + PADDING * 2
        for column in range(self.dump.columns):
            positions.append((x, cell_width))
            x += cell_width
        text_width = self.dump.columns * self.dump.width * self.char_width + PADDING * 2
        positions.append((x, text_width))
        x += text_width
        if self.dump.annotations:
            annotation_width = self.annotation_chars() * self.char_width + PADDING * 2
            positions.append((x, annotation_width))
            x += annotation_width
        return (positions, x)

    def update_size(self):
        """
        Work out how big the canvas needs to be.
        """
        (positions, width) = self.column_positions()
        self.canvas_width = width
        self.canvas_height = (self.dump.rows() + 1) * self.row_height
        self.canvas.set_size_request(self.canvas_width, self.canvas_height)
        self.canvas.queue_draw()

    def best_size(self):
        """
        The size the grid would like to be, including its scroll bars.
        """
        return (self.canvas_width + 20, self.canvas_height + 4)

    def row_cells(self, row):
        """
        The values, text and annotation of a row (cached).
        """
        if row not in self.row_cache:
            rowdata = self.dump.row_data(row)
            if not rowdata:
                rowvalues = [None] * self.dump.columns
                rowtext = ''
                rowannotation = ''
            else:
                rowvalues = self.dump.row_values(row)
                if len(rowvalues) < self.dump.columns:
                    rowvalues = list(rowvalues) + [None] * (self.dump.columns - len(rowvalues))
                rowtext = self.dump.format_chars(list(rowdata))
                rowannotation = self.dump.format_annotation(row)

            if len(self.row_cache) > self.config.row_cache_limit:
                self.row_cache = {}
            self.row_cache[row] = (rowvalues, rowtext, rowannotation)
        return self.row_cache[row]

    def cell_text(self, value):
        if value is None:
            return ''
        width = self.dump.width
        if width == 1:
            return '{:02X}'.format(value)
        if width == 2:
            return '{:04X}'.format(value)
        if width == 4:
            return '{:08X}'.format(value)
        return str(value)

    def cell_colour_name(self, value):
        if value is None:
            return 'invalid'
        if self.dump.width == 1:
            return self.config.byte_colour[value]
        if self.dump.width == 4:
            return 'word'
        if self.dump.width == 2:
            return 'halfword'
        return 'invalid'

    # Drawing

    def draw_text(self, context, x, y, width, text, colour, align_right=False):
        layout = self.canvas.create_pango_layout(text)
        layout.set_font_description(self.font)
        (text_width, text_height) = layout.get_pixel_size()
        if align_right:
            x = x + width - text_width - PADDING
        else:
            x = x + PADDING
        context.set_source_rgba(colour.red, colour.green, colour.blue, colour.alpha)
        context.move_to(x, y + 1)
        PangoCairo.show_layout(context, layout)
        return text_width

    def fill(self, context, x, y, width, height, colour):
        context.set_source_rgba(colour.red, colour.green, colour.blue, colour.alpha)
        context.rectangle(x, y, width, height)
        context.fill()

    def on_draw(self, widget, context):
        try:
            self.draw(context)
        except Exception as exc:
            import traceback
            traceback.print_exc()
        return False

    def draw(self, context):
        (positions, total_width) = self.column_positions()
        (clip_x1, clip_y1, clip_x2, clip_y2) = context.clip_extents()
        rows = self.dump.rows()
        first_row = max(int(clip_y1 // self.row_height) - 1, 0)
        last_row = min(int(clip_y2 // self.row_height), rows)
        columns = self.dump.columns
        width = self.canvas_width
        invalid = self.colours['invalid']

        # The headings are the first row
        heading_background = self.colours['plain'][0]
        self.fill(context, 0, 0, width, self.row_height, heading_background)
        headings = self.dump.headings()
        text_colour = self.colours['plain'][1]
        for (index, heading) in enumerate(headings):
            (x, cell_width) = positions[index + 1]
            self.draw_text(context, x, 0, cell_width, heading, text_colour, align_right=(index < columns))

        for row in range(first_row, last_row):
            y = (row + 1) * self.row_height
            (rowvalues, rowtext, rowannotation) = self.row_cells(row)

            # The label
            (x, label_width) = positions[0]
            self.fill(context, x, y, label_width, self.row_height, heading_background)
            self.draw_text(context, x, y, label_width,
                           self.dump.format_address(self.dump.row_to_offset(row)).upper(), text_colour,
                           align_right=True)

            for column in range(columns):
                (x, cell_width) = positions[column + 1]
                value = rowvalues[column]
                (background, foreground) = self.colours[self.cell_colour_name(value)]
                if self.cursor == (row, column):
                    background = self.colours['cursor'][0]
                self.fill(context, x, y, cell_width, self.row_height, background)
                if value is not None:
                    self.draw_text(context, x, y, cell_width, self.cell_text(value), foreground,
                                   align_right=True)

            # The text
            (x, text_width) = positions[columns + 1]
            (background, foreground) = self.colours['text']
            self.fill(context, x, y, text_width, self.row_height, background)
            self.draw_text(context, x, y, text_width, rowtext, foreground)

            if self.dump.annotations:
                (x, annotation_width) = positions[columns + 2]
                (background, foreground) = self.colours['annotation']
                self.fill(context, x, y, annotation_width, self.row_height, background)
                self.draw_annotation(context, x, y, annotation_width, rowannotation, foreground)

            if self.config.has_grid:
                grid = self.colours['grid'][0]
                context.set_source_rgba(grid.red, grid.green, grid.blue, grid.alpha)
                context.rectangle(0, y, width, 1)
                context.fill()

    def draw_annotation(self, context, x, y, width, annotation, foreground):
        """
        An annotation is text, or a list of text and (colour, text) parts to be drawn in turn.
        """
        if not annotation:
            return
        if isinstance(annotation, str):
            annotation = [annotation]
        offset = 0
        for part in annotation:
            if isinstance(part, str):
                colour = foreground
                text = part
            else:
                colour = to_rgba(part[0]) or foreground
                text = part[1]
            offset += self.draw_text(context, x + offset, y, width - offset, text, colour)

    # Cells and the pointer

    def cell_at(self, x, y):
        """
        Convert a position in the canvas to (row, column), where column is None outside the data.
        """
        row = int(y // self.row_height) - 1
        (positions, total_width) = self.column_positions()
        column = None
        for index in range(self.dump.columns):
            (cx, cell_width) = positions[index + 1]
            if cx <= x < cx + cell_width:
                column = index
                break
        return (row, column)

    def offset_of(self, row, column):
        if row < 0 or column is None:
            return None
        offset = self.dump.row_to_offset(row) + column * self.dump.width
        if offset >= len(self.dump.data):
            return None
        return offset

    def on_motion(self, widget, event):
        cell = self.cell_at(event.x, event.y)
        if cell != self.last_mouse_over:
            self.last_mouse_over = cell
            self.config.mouse_over(self.offset_of(*cell))
        return False

    def on_leave(self, widget, event):
        self.last_mouse_over = None
        self.config.mouse_over(None)
        return False

    def on_button_press(self, widget, event):
        self.canvas.grab_focus()
        if event.button == 1:
            (row, column) = self.cell_at(event.x, event.y)
            if column is not None and row >= 0 and self.offset_of(row, column) is not None:
                self.cursor = (row, column)
                self.canvas.queue_draw()
        elif event.button == 3:
            self.popup_menu(event)
            return True
        return False

    def on_key(self, widget, event):
        control = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        if control and event.keyval in (Gdk.KEY_f, Gdk.KEY_F) and self.config.has_find_string:
            self.on_find_string()
            return True
        if control and event.keyval in (Gdk.KEY_l, Gdk.KEY_L) and self.config.has_goto_address:
            self.on_goto_address()
            return True
        return False

    # The menu

    def build_menu(self):
        self.menu = Gtk.Menu()
        self.item_bytes = self.item_halfwords = self.item_words = None
        if self.config.has_width_1:
            self.item_bytes = self.add_check_item("Bytes", lambda item: self.width_chosen(item, 1))
        if self.config.has_width_2:
            self.item_halfwords = self.add_check_item("Half words", lambda item: self.width_chosen(item, 2))
        if self.config.has_width_4:
            self.item_words = self.add_check_item("Words", lambda item: self.width_chosen(item, 4))

        if self.config.menu_format:
            if len(self.menu.get_children()) > 0:
                self.menu.append(Gtk.SeparatorMenuItem())
            for item in self.config.menu_format:
                self.add_configured_item(item)

        if self.config.has_goto_address or self.config.has_find_string or self.config.menu_extra:
            if len(self.menu.get_children()) > 0:
                self.menu.append(Gtk.SeparatorMenuItem())
        if self.config.has_goto_address:
            self.add_plain_item("Goto address...", self.on_goto_address, record=True)
        if self.config.has_find_string:
            self.add_plain_item("Find string...", self.on_find_string, record=True)
        for item in self.config.menu_extra:
            self.add_configured_item(item)

        self.item_savedata = None
        if self.config.has_save_data:
            if len(self.menu.get_children()) > 0:
                self.menu.append(Gtk.SeparatorMenuItem())
            self.item_savedata = self.add_plain_item("Save data...", self.on_save_data)
        self.menu.show_all()

    def add_check_item(self, name, handler):
        item = Gtk.CheckMenuItem(label=name)
        item.connect("activate", handler)
        self.menu.append(item)
        return item

    def add_plain_item(self, name, handler, record=False):
        item = Gtk.MenuItem(label=name)
        item.connect("activate", lambda item: handler())
        self.menu.append(item)
        if record:
            self.menu_items.append((item, name, lambda *args, **kwargs: handler(), False))
        return item

    def add_configured_item(self, definition):
        name = definition[0]
        func = definition[1]
        checked = definition[2] if len(definition) > 2 else False
        if checked:
            item = Gtk.CheckMenuItem(label=name)
        else:
            item = Gtk.MenuItem(label=name)
        item.connect("activate", lambda item, func=func, checked=checked: self.configured_chosen(item, func, checked))
        self.menu.append(item)
        self.menu_items.append((item, name, func, checked))

    def configured_chosen(self, item, func, checked):
        if checked and self.updating_menu:
            return
        func(self, self.dump, chosen=True)

    updating_menu = False

    def width_chosen(self, item, width):
        if self.updating_menu:
            return
        self.set_width(width)

    def popup_menu(self, event):
        self.updating_menu = True
        try:
            if self.item_bytes:
                self.item_bytes.set_active(self.dump.width == 1)
            if self.item_halfwords:
                self.item_halfwords.set_active(self.dump.width == 2)
            if self.item_words:
                self.item_words.set_active(self.dump.width == 4)
            for (item, name, func, checked) in self.menu_items:
                if checked:
                    item.set_active(bool(func(self, self.dump, chosen=False)))
        finally:
            self.updating_menu = False
        self.menu.popup_at_pointer(event)

    # The DumpGridBase interface

    def set_data(self, data):
        self.dump.data = data
        self.row_cache = {}
        self.cursor = None
        self.update_size()
        if self.frame:
            self.frame.fit()

    def refresh(self):
        self.row_cache = {}
        self.canvas.queue_draw()

    def visible_range(self):
        vadjustment = self.get_vadjustment()
        top = vadjustment.get_value()
        height = vadjustment.get_page_size()
        first = max(int(top // self.row_height) - 1, 0)
        last = min(int((top + height) // self.row_height) - 1, max(self.dump.rows() - 1, 0))
        return (0, first, self.dump.columns, last)

    def scroll_to_row(self, row):
        self.get_vadjustment().set_value(row * self.row_height)

    def set_width(self, width):
        self.dump.columns = int(self.dump.width * self.dump.columns / width)
        self.dump.width = width
        self.row_cache = {}
        self.update_size()
        if self.frame:
            self.frame.fit()

    def set_columns(self, columns):
        self.dump.columns = columns
        self.row_cache = {}
        self.update_size()
        if self.frame:
            self.frame.fit()

    # Finding things

    def goto_address(self, address):
        """
        Move the cursor to an address and scroll to it.
        """
        (row, column) = self.dump.address_to_coords(address)
        if row is None:
            return
        self.cursor = (row, min(column // self.dump.width, self.dump.columns - 1))
        self.scroll_to_row(row)
        self.canvas.queue_draw()

    def get_address(self):
        if self.cursor is None:
            return self.dump.address_base
        offset = self.offset_of(*self.cursor)
        return (offset or 0) + self.dump.address_base

    def find_string(self, text):
        """
        Find a string in the data after the cursor.

        @return: the address it was found at, or None
        """
        start = 0
        if self.cursor is not None:
            start = (self.offset_of(*self.cursor) or 0) + 1
        data = self.dump.data
        found = data.find(text.encode('latin-1'), start)
        if found < 0:
            found = data.find(text.encode('latin-1'), 0)
        if found < 0:
            return None
        return found + self.dump.address_base

    def ask(self, title, prompt, default):
        dialog = Gtk.Dialog(title=title, transient_for=self.get_toplevel() if isinstance(self.get_toplevel(), Gtk.Window) else None)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("OK", Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_spacing(6)
        box.set_border_width(6)
        box.pack_start(Gtk.Label(label=prompt), False, False, 0)
        entry = Gtk.Entry()
        entry.set_text(default)
        entry.set_activates_default(True)
        box.pack_start(entry, False, False, 0)
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.show_all()
        response = dialog.run()
        text = entry.get_text()
        dialog.destroy()
        return text if response == Gtk.ResponseType.OK else None

    def on_goto_address(self):
        start = self.dump.address_base
        end = self.dump.address_base + len(self.dump.data)
        text = self.ask("Goto address", "Address to go to (&{:X} - &{:X}):".format(start, end),
                        "&{:X}".format(self.get_address()))
        if not text:
            return
        text = text.strip()
        if text[:1] == '&':
            text = text[1:]
        if text[:2].lower() == '0x':
            text = text[2:]
        try:
            self.goto_address(int(text, 16))
        except ValueError:
            pass

    def on_find_string(self):
        text = self.ask("Find string", "String to find:", self.last_find_string)
        if not text:
            return
        self.last_find_string = text
        address = self.find_string(text)
        if address is not None:
            self.goto_address(address)

    def on_save_data(self):
        dialog = Gtk.FileChooserDialog(title="Save data", action=Gtk.FileChooserAction.SAVE)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", Gtk.ResponseType.OK)
        dialog.set_current_name(self.config.default_savedata_filename)
        dialog.set_do_overwrite_confirmation(True)
        response = dialog.run()
        filename = dialog.get_filename()
        dialog.destroy()
        if response == Gtk.ResponseType.OK and filename:
            with open(filename, 'wb') as fh:
                fh.write(bytes(self.dump.data))


class DumpFrame(Gtk.Window):
    """
    A window which can display arbitrary data.
    """

    def __init__(self, title="Hex Dumper", data=b'', config=None):
        super(DumpFrame, self).__init__(title=title)
        self.config = config or dumpconfig.DumpConfig()
        self.data = data

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.statusbar = None
        if self.config.frame_statusbar:
            self.statusbar = Gtk.Statusbar()
            self.config.mouse_over = self.update_statusbar

        self.grid = DumpGrid(self.GetDumpData(), config=self.config, frame=self)
        box.pack_start(self.grid, True, True, 0)
        if self.statusbar:
            box.pack_start(self.statusbar, False, False, 0)
        self.add(box)
        self.fit()

    def fit(self):
        (width, height) = self.grid.best_size()
        height = min(height, self.config.frame_max_height)
        self.set_default_size(width, height + (30 if self.statusbar else 0))

    def update_statusbar(self, offset):
        """
        Called when the mouse is over a new cell.

        @param offset:  Data offset, or None if the pointer has moved out of the grid.
        """
        self.statusbar.pop(0)
        if offset is not None:
            self.statusbar.push(0, self.config.cellinfo(offset) or '')

    def GetDumpData(self):
        return self.data
