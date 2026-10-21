#!/usr/bin/env python3
"""A small native Wayland browser; WebKit owns HTML, JS, networking and storage."""
import sys
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, Gio, Gtk, Pango, WebKit2
from browser_policy import address, profile_paths


class BrowserWindow(Gtk.ApplicationWindow):
    def __init__(self, application, context, urls):
        super().__init__(application=application)
        self.context = context
        self.set_default_size(1100, 750)
        self.set_title("Loopy Browser")
        self.connect("key-press-event", self.key)
        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(layout)
        toolbar = Gtk.Box(spacing=6)
        toolbar.set_border_width(6)
        layout.pack_start(toolbar, False, False, 0)
        self.back = self.button(toolbar, "←", "뒤로 · Alt+Left", lambda: self.view.go_back())
        self.forward = self.button(toolbar, "→", "앞으로 · Alt+Right", lambda: self.view.go_forward())
        self.button(toolbar, "↻", "새로고침 · Ctrl+R", lambda: self.view.reload())
        self.location = Gtk.Entry()
        self.location.set_placeholder_text("주소 또는 검색어 · Ctrl+L")
        self.location.connect("activate", self.navigate)
        toolbar.pack_start(self.location, True, True, 0)
        self.button(toolbar, "+", "새 탭 · Ctrl+T", lambda: self.new_tab("about:blank"))
        self.tabs = Gtk.Notebook()
        self.tabs.set_scrollable(True)
        self.tabs.connect_after("switch-page", self.switched)
        layout.pack_start(self.tabs, True, True, 0)
        self.message = Gtk.Label(xalign=0)
        self.message.set_margin_start(8)
        layout.pack_start(self.message, False, False, 0)
        for url in urls:
            self.new_tab(url)
        self.show_all()
        self.message.hide()

    @property
    def view(self):
        return self.tabs.get_nth_page(self.tabs.get_current_page())

    def button(self, toolbar, text, hint, action):
        button = Gtk.Button(label=text)
        button.set_tooltip_text(hint)
        button.set_can_focus(False)
        button.connect("clicked", lambda _button: action())
        toolbar.pack_start(button, False, False, 0)
        return button

    def new_tab(self, url, related=None):
        view = (WebKit2.WebView.new_with_related_view(related) if related is not None
                else WebKit2.WebView.new_with_context(self.context))
        view.get_settings().set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.NEVER)
        title = Gtk.Label(label="새 탭")
        title.set_width_chars(14)
        title.set_max_width_chars(28)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        label = Gtk.Box(spacing=6)
        label.pack_start(title, True, True, 0)
        close = Gtk.Button(label="×")
        close.set_relief(Gtk.ReliefStyle.NONE)
        close.set_can_focus(False)
        close.set_tooltip_text("탭 닫기 · Ctrl+W")
        close.connect("clicked", lambda _button: self.close_tab(view))
        label.pack_start(close, False, False, 0)
        label.show_all()
        view.connect("notify::title", lambda widget, _spec: self.title_changed(widget, title))
        view.connect("notify::uri", lambda widget, _spec: self.sync(widget))
        view.connect("load-changed", lambda widget, _event: self.sync(widget))
        view.connect("load-failed", self.load_failed)
        view.connect("create", lambda widget, _action: self.new_tab(None, related=widget))
        view.connect("close", lambda widget: self.close_tab(widget))
        view.connect("web-process-terminated", lambda _widget, _reason: self.error("페이지 실행이 종료됐습니다. 새로고침으로 다시 여세요."))
        index = self.tabs.append_page(view, label)
        view.show()
        self.tabs.set_current_page(index)
        if url is not None:
            view.load_uri(address(url))
        view.grab_focus()
        if url == "about:blank":
            self.focus_address()
        return view

    def title_changed(self, view, label):
        label.set_text(view.get_title() or "새 탭")
        self.sync(view)

    def sync(self, view):
        if view != self.view:
            return
        self.set_title((view.get_title() or "새 탭") + " · Loopy Browser")
        if not self.location.has_focus():
            self.location.set_text(view.get_uri() or "")
        self.back.set_sensitive(view.can_go_back())
        self.forward.set_sensitive(view.can_go_forward())

    def switched(self, _notebook, view, _index):
        self.location.set_text(view.get_uri() or "")
        self.sync(view)

    def close_tab(self, view):
        index = self.tabs.page_num(view)
        if index < 0:
            return
        self.tabs.remove_page(index)
        view.destroy()
        if self.tabs.get_n_pages() == 0:
            self.destroy()
        else:
            self.view.grab_focus()

    def focus_address(self):
        self.location.grab_focus()
        self.location.select_region(0, -1)

    def navigate(self, entry):
        try:
            url = address(entry.get_text())
        except ValueError as failure:
            self.error(str(failure))
            return
        self.message.hide()
        self.view.load_uri(url)
        self.view.grab_focus()

    def error(self, text):
        self.message.set_text(text)
        self.message.show()

    def load_failed(self, _view, _event, _uri, failure):
        # Stop/cancel navigation is not a failed page.
        if failure.matches(WebKit2.network_error_quark(), WebKit2.NetworkError.CANCELLED):
            return False
        self.error("페이지를 열지 못했습니다: " + failure.message)
        return False

    def key(self, _window, event):
        # Handle browser shortcuts before GTK sends them to WebKit's asynchronous
        # fallback. Address focus must not consume the next page key afterwards.
        state = event.state
        control = bool(state & Gdk.ModifierType.CONTROL_MASK)
        alt = bool(state & Gdk.ModifierType.MOD1_MASK)
        letter = Gdk.keyval_to_lower(event.keyval)
        if control and not alt:
            actions = {Gdk.KEY_l: self.focus_address, Gdk.KEY_t: lambda: self.new_tab("about:blank"),
                       Gdk.KEY_w: lambda: self.close_tab(self.view), Gdk.KEY_r: self.view.reload}
            if letter in actions:
                actions[letter]()
                return True
            if event.keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
                delta = -1 if state & Gdk.ModifierType.SHIFT_MASK else 1
                self.tabs.set_current_page((self.tabs.get_current_page() + delta) % self.tabs.get_n_pages())
                self.view.grab_focus()
                return True
        if alt and not control and event.keyval in (Gdk.KEY_Left, Gdk.KEY_Right):
            (self.view.go_back if event.keyval == Gdk.KEY_Left else self.view.go_forward)()
            return True
        if event.keyval == Gdk.KEY_Escape and self.location.has_focus():
            self.view.grab_focus()
            return True
        if event.keyval == Gdk.KEY_F5:
            self.view.reload()
            return True
        return False


def main(urls):
    data, cache = profile_paths()
    for folder in (data, cache):
        folder.mkdir(parents=True, mode=0o700, exist_ok=True)
    manager = WebKit2.WebsiteDataManager(base_data_directory=str(data), base_cache_directory=str(cache))
    manager.get_cookie_manager().set_persistent_storage(str(data / "cookies.sqlite"), WebKit2.CookiePersistentStorage.SQLITE)
    context = WebKit2.WebContext.new_with_website_data_manager(manager)
    # PRoot has no Linux namespace isolation. Android UID/SELinux/inherited
    # process policy are the boundary; there is no additional browser sandbox.
    context.set_sandbox_enabled(False)
    app = Gtk.Application(application_id="dev.loopy.browser", flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.connect("activate", lambda application: BrowserWindow(application, context, urls or ["about:blank"]).present())
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
