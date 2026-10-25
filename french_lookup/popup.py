import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
import re

from gi.repository import Gdk, GdkX11, GLib, Gtk

CSS = b"""
#fl-popup { background: #1e2230; border: 1px solid #3b4252; }
#fl-popup label { color: #e5e9f0; font-size: 10pt; }
#fl-title { font-weight: bold; font-size: 11pt; color: #88c0d0; }
#fl-hint { color: #7b8394; font-size: 8.5pt; }
#fl-status { color: #a3be8c; font-weight: bold; }
#fl-rule { background: #3b4252; min-height: 1px; }
"""

OFFSET = 14
LABEL_COLOR = "#ebcb8b"
POINT = re.compile(r"^([A-Za-zÀ-ÿ' ]{2,20}):\s*(.*)$")


def point_markup(line: str) -> str:
    """'Rule: passé composé' → bold coloured label + text, with a little extra line height."""
    m = POINT.match(line)
    if m:
        label, text = GLib.markup_escape_text(m.group(1)), GLib.markup_escape_text(m.group(2))
        body = f'<span foreground="{LABEL_COLOR}" weight="bold">{label}</span>   {text}'
    else:
        body = GLib.markup_escape_text(line)
    return f'<span line_height="1.2">{body}</span>'


def install_css():
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


class Popup(Gtk.Window):
    """Loading → answer (Enter saves, Esc closes) or message-only."""

    def __init__(self, title: str, on_save=None, on_closed=None):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_name("fl-popup")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.on_save = on_save
        self.on_closed = on_closed
        self.answer = None
        self.closing = False

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(16)
        self.add(box)

        head = Gtk.Label(label=title if len(title) <= 60 else title[:57] + "…", xalign=0)
        head.set_name("fl-title")
        box.pack_start(head, False, False, 0)
        rule = Gtk.Box()
        rule.set_name("fl-rule")
        box.pack_start(rule, False, False, 0)

        row = Gtk.Box(spacing=8)
        self.spinner = Gtk.Spinner()
        self.body = Gtk.Label(xalign=0)
        self.body.set_line_wrap(True)
        self.body.set_max_width_chars(50)
        row.pack_start(self.spinner, False, False, 0)
        row.pack_start(self.body, True, True, 0)
        box.pack_start(row, False, False, 0)
        self.row = row

        self.points = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.pack_start(self.points, False, False, 0)

        self.hint = Gtk.Label(xalign=1)
        self.hint.set_name("fl-hint")
        box.pack_start(self.hint, False, False, 0)

        self.connect("key-press-event", self._on_key)
        self.connect("focus-out-event", lambda *_: self.close_popup())
        self.connect("destroy", lambda *_: self.on_closed and self.on_closed(self))

        self._pointer = Gdk.Display.get_default().get_default_seat().get_pointer().get_position()[1:]

    # --- states -------------------------------------------------------------

    def show_loading(self):
        self.body.set_text("Asking Claude…")
        self.hint.set_text("Esc = cancel")
        self.spinner.start()
        self._show()

    def show_answer(self, answer: str):
        self.answer = answer
        self.spinner.stop()
        self.row.hide()
        for line in answer.splitlines():
            label = Gtk.Label(xalign=0)
            label.set_markup(point_markup(line))
            label.set_line_wrap(True)
            label.set_max_width_chars(50)
            self.points.pack_start(label, False, False, 0)
        self.points.show_all()
        self.hint.set_text("Enter = save card  ·  Esc = close")
        self._reposition()

    def show_message(self, message: str):
        self.answer = None
        self.spinner.stop()
        self.spinner.hide()
        self.body.set_text(message)
        self.hint.set_text("Esc = close")
        if self.get_visible():
            self._reposition()
        else:
            self._show()

    # --- window plumbing ----------------------------------------------------

    def _show(self):
        self.show_all()
        if not self.spinner.get_property("active"):
            self.spinner.hide()
        self._reposition()
        # A fresh X server timestamp lets mutter grant focus despite focus-stealing prevention.
        self.present_with_time(GdkX11.x11_get_server_time(self.get_window()))

    def _reposition(self):
        self.resize(1, 1)
        GLib.idle_add(self._place)

    def _place(self):
        x, y = self._pointer
        display = Gdk.Display.get_default()
        area = display.get_monitor_at_point(x, y).get_workarea()
        w, h = self.get_size()
        x = min(x + OFFSET, area.x + area.width - w - 4)
        y = y + OFFSET if y + OFFSET + h <= area.y + area.height else y - OFFSET - h
        self.move(max(area.x, x), max(area.y, y))
        return False

    def _on_key(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.close_popup()
        elif event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and self.answer and not self.closing:
            saved = self.on_save(self.answer) if self.on_save else False
            self.closing = True
            self.hint.set_text("")
            self.points.hide()
            self.row.show()
            self.spinner.hide()
            self.body.set_name("fl-status")
            self.body.set_text("Saved ✓" if saved else "Already saved")
            self._reposition()
            GLib.timeout_add(600, self.close_popup)
        return True

    def close_popup(self, *_):
        if not self.in_destruction():
            self.destroy()
        return False
