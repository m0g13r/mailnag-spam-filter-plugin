import gi
import re
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
from Mailnag.common.plugins import Plugin, HookTypes
from Mailnag.common.i18n import _
plugin_defaults = {
    'whitelist' : 'boss@company.com',
    'keywords' : 'newsletter, viagra, casino, bitcoin, crypto',
    'regex' : '(id|ref|nr|fall)[\\s:#-]?[a-z0-9-]{4,}',
    'tlds' : 'xyz, top, click, link',
    'threshold' : 5,
    'weight_kw' : 2,
    'weight_rx' : 3,
    'weight_tl' : 5
}
class SpamfilterPlugin(Plugin):
    def __init__(self):
        self._filter_mails_hook = None
        self._whitelist_re = None
        self._kw_re = None
        self._rx_re = None
        self._tl_re = None
        self._cfg_vals = {}
    def _split_smart(self, text):
        if not text: return []
        lines = text.splitlines()
        final_patterns = []
        for line in lines:
            line = line.strip()
            if not line: continue
            if ',' in line and not re.search(r'\{.*,.*\}', line):
                final_patterns.extend([p.strip() for p in line.split(',') if p.strip()])
            else:
                final_patterns.append(line)
        return final_patterns
    def enable(self):
        config = self.get_config()
        for k, d in [('threshold', 5), ('weight_kw', 2), ('weight_rx', 3), ('weight_tl', 5)]:
            val = int(config.get(k, d))
            self._cfg_vals[k] = max(0, min(val, 20 if k == 'threshold' else 10))
        wl_raw = self._split_smart(config.get('whitelist', plugin_defaults['whitelist']))
        if wl_raw:
            wl_p = [re.escape(w.lower().strip()) + '$' if '@' in w else f'@{re.escape(w.lower().strip())}$' for w in wl_raw if w.strip()]
            if wl_p: self._whitelist_re = re.compile('|'.join(wl_p), re.I)
        def comp(key):
            raw = self._split_smart(config.get(key, ''))
            if key == 'tlds': raw = [f'\\.{re.escape(t.lstrip("."))}\\b' for t in raw if t.strip()]
            valid = [p for p in raw if self._is_valid(p)]
            return re.compile('|'.join(valid), re.I) if valid else None
        self._kw_re = comp('keywords')
        self._rx_re = comp('regex')
        self._tl_re = comp('tlds')
        self._filter_mails_hook = lambda mails: [m for m in mails if not self._is_filtered(m)]
        self.get_mailnag_controller().get_hooks().register_hook_func(HookTypes.FILTER_MAILS, self._filter_mails_hook)
    def _is_valid(self, p):
        try:
            re.compile(p, re.I)
            return True
        except: return False
    def disable(self):
        if self._filter_mails_hook:
            self.get_mailnag_controller().get_hooks().unregister_hook_func(HookTypes.FILTER_MAILS, self._filter_mails_hook)
            self._filter_mails_hook = None
    def get_manifest(self):
        return (_("Advanced Spam Filter"), _("Granular weighted scoring spam filter."), "4.0", "User")
    def get_default_config(self):
        return plugin_defaults
    def has_config_ui(self):
        return True
    def get_config_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_border_width(10)
        top_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        top_hbox.pack_start(Gtk.Label(label=_("Global Spam Threshold (1-20):"), xalign=0), False, False, 0)
        adj_t = Gtk.Adjustment(value=5, lower=1, upper=20, step_increment=1)
        spin_t = Gtk.SpinButton(adjustment=adj_t, name='threshold')
        top_hbox.pack_start(spin_t, False, False, 0)
        main_box.pack_start(top_hbox, False, False, 0)
        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        main_box.pack_start(grid, True, True, 0)
        def add_row(label_text, weight_name, tv_name, row, def_w=0):
            header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            header_box.pack_start(Gtk.Label(label=_(label_text), xalign=0, hexpand=True), True, True, 0)
            if weight_name:
                header_box.pack_start(Gtk.Label(label=_("Weight (0-10):"), xalign=1), False, False, 0)
                adj = Gtk.Adjustment(value=def_w, lower=0, upper=10, step_increment=1)
                spin = Gtk.SpinButton(adjustment=adj, name=weight_name)
                header_box.pack_start(spin, False, False, 0)
            grid.attach(header_box, 0, row * 2, 1, 1)
            sw = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN, hexpand=True, vexpand=True)
            sw.set_size_request(-1, 70)
            tv = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD, name=tv_name)
            sw.add(tv)
            grid.attach(sw, 0, row * 2 + 1, 1, 1)
        add_row("Whitelist (Always Allow):", None, "wl", 0)
        add_row("Keywords:", "weight_kw", "kw", 1, 2)
        add_row("Regex Patterns:", "weight_rx", "rx", 2, 3)
        add_row("Blocked TLDs:", "weight_tl", "tl", 3, 5)
        main_box.show_all()
        return main_box
    def load_ui_from_config(self, ui):
        c = self.get_config()
        for k in ['threshold', 'weight_kw', 'weight_rx', 'weight_tl']:
            w = self._find_w(ui, k)
            if w: w.set_value(float(c.get(k, plugin_defaults[k])))
        for k, n in [('whitelist', 'wl'), ('keywords', 'kw'), ('regex', 'rx'), ('tlds', 'tl')]:
            tv = self._find_w(ui, n)
            if tv: tv.get_buffer().set_text(str(c.get(k, plugin_defaults.get(k, ''))))
    def save_ui_to_config(self, ui):
        c = self.get_config()
        for k in ['threshold', 'weight_kw', 'weight_rx', 'weight_tl']:
            w = self._find_w(ui, k)
            if w: c[k] = int(w.get_value())
        for k, n in [('whitelist', 'wl'), ('keywords', 'kw'), ('regex', 'rx'), ('tlds', 'tl')]:
            tv = self._find_w(ui, n)
            if tv:
                b = tv.get_buffer()
                raw = b.get_text(b.get_start_iter(), b.get_end_iter(), False)
                items = sorted(list(set(self._split_smart(raw))))
                c[k] = '\n'.join(items)
                b.set_text(c[k])
    def _find_w(self, widget, name):
        if widget.get_name() == name: return widget
        if isinstance(widget, Gtk.Container):
            for c in widget.get_children():
                res = self._find_w(c, name)
                if res: return res
        return None
    def _is_filtered(self, mail):
        addr = (getattr(mail, 'sender', ('', ''))[1] or '').lower()
        if self._whitelist_re and self._whitelist_re.search(addr): return False
        score = 0
        name = getattr(mail, 'sender', ('',''))[0]
        subject = getattr(mail, 'subject', '')
        body = getattr(mail, 'content', '') or getattr(mail, 'snippet', '')
        content = f"{name} {addr} {subject} {body}"
        if self._kw_re and self._kw_re.search(content): score += self._cfg_vals.get('weight_kw', 2)
        if self._rx_re and self._rx_re.search(content): score += self._cfg_vals.get('weight_rx', 3)
        if self._tl_re and self._tl_re.search(content): score += self._cfg_vals.get('weight_tl', 5)
        return score >= self._cfg_vals.get('threshold', 5)
