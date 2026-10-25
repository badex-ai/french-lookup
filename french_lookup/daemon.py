"""Background app: listens for triggers, reads the selection, shows the popup, owns the tray icon."""

import os
import signal
import sys
import threading

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from . import claude, config
from .client import running
from .cards import CardStore
from .config import DATA_DIR, SOCKET_PATH
from .popup import Popup, install_css

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator
except (ValueError, ImportError):
    AppIndicator = None


class App:
    def __init__(self):
        self.cfg = config.load()
        self.store = CardStore(DATA_DIR, self.cfg.batch_size)
        self.popup = None
        self.proc = None
        self.generation = 0
        self.paused = False
        self.indicator = None

    # --- lookups ------------------------------------------------------------

    def on_trigger(self):
        Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY).request_text(lambda _c, text: self.lookup(text or ""))

    def lookup(self, raw: str):
        self._cancel()
        text = claude.clean_selection(raw)
        if self.paused:
            return self._message(text or "French lookup", "Paused. Resume from the tray icon.")
        if not text:
            return self._message("Nothing selected", "Highlight a word or phrase first, then press Super+F.")
        if len(text) > self.cfg.max_chars:
            return self._message(text, f"That's {len(text)} characters. Select at most {self.cfg.max_chars}.")

        self.popup = Popup(text, on_save=lambda answer: self._save(text, answer), on_closed=self._on_closed)
        self.popup.show_loading()
        self.generation += 1
        threading.Thread(target=self._run, args=(self.generation, text), daemon=True).start()

    def _run(self, generation: int, text: str):
        try:
            proc = claude.start(self.cfg, text)
            if generation != self.generation:  # superseded while starting
                os.killpg(proc.pid, signal.SIGTERM)
                return
            self.proc = proc
            answer, error = claude.wait(proc, self.cfg), None
        except claude.LookupError_ as e:
            answer, error = None, str(e)
        except Exception as e:  # show anything unexpected rather than hanging on "Asking Claude…"
            answer, error = None, f"Unexpected error: {e}"
        GLib.idle_add(self._finish, generation, answer, error)

    def _finish(self, generation, answer, error):
        if generation != self.generation or self.popup is None:
            return False
        if answer:
            self.popup.show_answer(answer)
        else:
            self.popup.show_message(error)
        return False

    def _message(self, title, message):
        self.popup = Popup(title, on_closed=self._on_closed)
        self.popup.show_message(message)

    def _cancel(self):
        self.generation += 1
        proc, self.proc = self.proc, None
        if proc and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if self.popup:
            popup, self.popup = self.popup, None
            popup.close_popup()

    def _on_closed(self, popup):
        if popup is self.popup:
            self._cancel()

    def _save(self, front, back) -> bool:
        saved = self.store.add(front, back)
        self._refresh_tray()
        return saved

    # --- tray ---------------------------------------------------------------

    def build_tray(self):
        if AppIndicator is None:
            print("french-lookup: tray icon unavailable (install gir1.2-ayatanaappindicator3-0.1)", file=sys.stderr)
            return
        self.indicator = AppIndicator.Indicator.new(
            "french-lookup", "accessories-dictionary-symbolic", AppIndicator.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_title("French lookup")
        self._refresh_tray()

    def _refresh_tray(self):
        """Rebuild the menu so the batch list is always current."""
        if self.indicator is None:
            return
        menu = Gtk.Menu()
        pause = Gtk.CheckMenuItem(label="Pause lookups")
        pause.set_active(self.paused)
        pause.connect("toggled", lambda item: setattr(self, "paused", item.get_active()))
        menu.append(pause)
        menu.append(Gtk.SeparatorMenuItem())

        batches = self.store.batches()
        size = self.store.batch_size
        if not batches:
            menu.append(_info("No cards saved yet"))
        for path, n in batches:
            menu.append(_info(f"{path.name}: {n} cards, ready" if n >= size else f"{path.name}: {n}/{size}, filling"))
        if batches:
            oldest = batches[0][0].name
            upload = Gtk.MenuItem(label=f"Mark {oldest} as uploaded")
            upload.connect("activate", lambda _: self._mark_uploaded())
            menu.append(upload)

        menu.append(Gtk.SeparatorMenuItem())
        open_item = Gtk.MenuItem(label="Open cards folder")
        open_item.connect("activate", lambda _: self._open_folder())
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda _: self.quit())
        menu.append(open_item)
        menu.append(quit_item)
        menu.show_all()
        self.indicator.set_menu(menu)
        self.menu = menu  # keep a reference so GTK doesn't drop it

    def _mark_uploaded(self):
        self.store.mark_oldest_uploaded()
        GLib.idle_add(self._refresh_tray)  # not while the old menu is still emitting

    def _open_folder(self):
        folder = self.store.batches_dir
        folder.mkdir(parents=True, exist_ok=True)
        Gio.AppInfo.launch_default_for_uri(folder.as_uri(), None)

    # --- lifecycle ----------------------------------------------------------

    def serve(self):
        SOCKET_PATH.unlink(missing_ok=True)
        self.service = Gio.SocketService()
        self.service.add_address(
            Gio.UnixSocketAddress.new(str(SOCKET_PATH)), Gio.SocketType.STREAM, Gio.SocketProtocol.DEFAULT
        )
        self.service.connect("incoming", self._on_incoming)
        self.service.start()

    def _on_incoming(self, _service, connection, _source):
        data = connection.get_input_stream().read_bytes(64, None).get_data()
        connection.close(None)
        if data.strip() == b"lookup":
            self.on_trigger()
        elif data.strip() == b"quit":
            self.quit()
        return True

    def quit(self, *_):
        self._cancel()
        SOCKET_PATH.unlink(missing_ok=True)
        Gtk.main_quit()
        return False


def _info(text: str) -> Gtk.MenuItem:
    item = Gtk.MenuItem(label=text)
    item.set_sensitive(False)
    return item


def run() -> int:
    if running():
        print("french-lookup: already running", file=sys.stderr)
        return 0
    GLib.set_prgname("french-lookup")
    GLib.set_application_name("French lookup")
    Gtk.init([])
    install_css()
    app = App()
    app.serve()
    app.build_tray()
    for sig in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, app.quit)
    Gtk.main()
    return 0
