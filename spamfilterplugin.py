import gi
import re

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
from Mailnag.common.plugins import Plugin, HookTypes
from Mailnag.common.i18n import _

plugin_defaults = {
    'whitelist': 'boss@company.com',
    'trusted': 'amazon.com, paypal.com, ebay.com, google.com, microsoft.com, apple.com, dhl.com',
    'keywords': 'newsletter, viagra, casino, bitcoin, crypto',
    'regex': r'(id|ref|nr|fall)[\s:#-]?[a-z0-9-]{4,}',
    'tlds': 'xyz, top, click, link, biz, info',
    'threshold': 5,
    'weight_kw': 2,
    'weight_rx': 3,
    'weight_tl': 5,
    'bonus_tr': 4
}

class SpamfilterPlugin(Plugin):

    def __init__(self):
        self._filter_mails_hook = None
        self._whitelist_re = None
        self._kw_super_re = None
        self._rx_res = []
        self._tl_set = set()
        self._trusted_domains = set()  # set für O(1)-Lookup
        self._trusted_emails = []
        self._cfg_vals = {}
        self._widgets = {}  # Widget-Cache

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
        for k, d in [('threshold', 5), ('weight_kw', 2), ('weight_rx', 3), ('weight_tl', 5), ('bonus_tr', 4)]:
            try:
                self._cfg_vals[k] = int(config.get(k, d))
            except (ValueError, TypeError):
                self._cfg_vals[k] = d

        # Häufig genutzte Werte als Attribute cachen → kein dict.get() im Hot-Path
        self._threshold  = self._cfg_vals['threshold']
        self._weight_kw  = self._cfg_vals['weight_kw']
        self._weight_rx  = self._cfg_vals['weight_rx']
        self._weight_tl  = self._cfg_vals['weight_tl']
        self._bonus_tr   = self._cfg_vals['bonus_tr']

        wl_raw = self._split_smart(config.get('whitelist', plugin_defaults['whitelist']))
        if wl_raw:
            wl_p = [re.escape(w.lower()) + '$' if '@' in w else f'@{re.escape(w.lower())}$' for w in wl_raw]
            self._whitelist_re = re.compile('|'.join(wl_p), re.I)

        tr_raw = self._split_smart(config.get('trusted', plugin_defaults['trusted']))
        self._trusted_emails = [t.lower() for t in tr_raw if '@' in t]
        self._trusted_domains = {t.lower() for t in tr_raw if '@' not in t}  # set → O(1)

        kw_raw = self._split_smart(config.get('keywords', ''))
        if kw_raw:
            self._kw_super_re = re.compile('|'.join([re.escape(k) for k in kw_raw]), re.I | re.UNICODE)

        tl_raw = self._split_smart(config.get('tlds', ''))
        self._tl_set = {t.lower().lstrip('.') for t in tl_raw}

        rx_raw = self._split_smart(config.get('regex', ''))
        self._rx_res = []
        for p in rx_raw:
            try: self._rx_res.append(re.compile(p, re.I | re.UNICODE))
            except re.error: continue

        self._filter_mails_hook = lambda mails: [m for m in mails if not self._is_filtered(m)]
        self.get_mailnag_controller().get_hooks().register_hook_func(HookTypes.FILTER_MAILS, self._filter_mails_hook)

    def disable(self):
        if self._filter_mails_hook:
            self.get_mailnag_controller().get_hooks().unregister_hook_func(HookTypes.FILTER_MAILS, self._filter_mails_hook)
            self._filter_mails_hook = None

    def get_manifest(self):
        return (_("Advanced Spam Filter Ultra"), _("Weighted scoring with clean functional tooltips."), "4.1", "User")

    def get_default_config(self): return plugin_defaults

    def has_config_ui(self): return True

    def get_config_ui(self):
        self._widgets = {}  # Cache zurücksetzen
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, border_width=10)
        
        top_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        lbl_p = Gtk.Label(label=_("Preset:"), xalign=0)
        top_hbox.pack_start(lbl_p, False, False, 0)
        
        preset_combo = Gtk.ComboBoxText(name='preset_combo')
        preset_combo.append("custom", _("Custom"))
        preset_combo.append("high", _("High (Aggressive)"))
        preset_combo.append("medium", _("Medium (Default)"))
        preset_combo.append("low", _("Low (Relaxed)"))
        preset_combo.set_active_id("custom")
        top_hbox.pack_start(preset_combo, False, False, 0)
        self._widgets['preset_combo'] = preset_combo
        
        top_hbox.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 5)

        lbl_t = Gtk.Label(label=_("Global Spam Threshold:"), xalign=0)
        top_hbox.pack_start(lbl_t, False, False, 0)
        
        adj_t = Gtk.Adjustment(value=5, lower=1, upper=20, step_increment=1)
        spin_t = Gtk.SpinButton(adjustment=adj_t, name='threshold')
        spin_t.set_tooltip_text(_("Total score limit for filtering."))
        top_hbox.pack_start(spin_t, False, False, 0)
        self._widgets['threshold'] = spin_t
        main_box.pack_start(top_hbox, False, False, 0)

        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 5)
        grid = Gtk.Grid(column_spacing=10, row_spacing=6)
        main_box.pack_start(grid, True, True, 0)

        self._preset_changing = False

        def add_row(label_text, value_name, tv_name, row, help_txt, def_val=0, is_bonus=False):
            hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            lbl = Gtk.Label(label=_(label_text), xalign=0, hexpand=True)
            hb.pack_start(lbl, True, True, 0)
            
            if value_name:
                hb.pack_start(Gtk.Label(label=_("Bonus (-):") if is_bonus else _("Weight (+):"), xalign=1), False, False, 0)
                adj = Gtk.Adjustment(value=def_val, lower=0, upper=20 if is_bonus else 10, step_increment=1)
                spin = Gtk.SpinButton(adjustment=adj, name=value_name)
                spin.set_tooltip_text(_("Score impact value."))
                hb.pack_start(spin, False, False, 0)
                self._widgets[value_name] = spin
            
            grid.attach(hb, 0, row * 2, 1, 1)
            sw = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN, hexpand=True, vexpand=True, height_request=60)
            tv = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD, name=tv_name)
            tv.set_tooltip_text(help_txt)
            sw.add(tv); grid.attach(sw, 0, row * 2 + 1, 1, 1)
            self._widgets[tv_name] = tv

        add_row("Whitelist:", None, "wl", 0, 
                _("Bypasses all filters."))
        add_row("Trusted Sources:", "bonus_tr", "tr", 1, 
                _("Subtracts from score (Emails = 2x, Domains = 1x)."), 4, True)
        add_row("Spam Keywords:", "weight_kw", "kw", 2, 
                _("Simple strings (Subject = 2x weight)."), 2)
        add_row("Regex Patterns:", "weight_rx", "rx", 3, 
                _("Complex patterns in name, subject, or body."), 3)
        add_row("Blocked TLDs:", "weight_tl", "tl", 4, 
                _("Suspicious extensions (e.g., .xyz)."), 5)

        def on_preset_changed(combo):
            if getattr(self, '_preset_changing', False): return
            self._preset_changing = True
            preset = combo.get_active_id()
            if preset == "high":
                self._widgets['threshold'].set_value(3)
                self._widgets['bonus_tr'].set_value(2)
                self._widgets['weight_kw'].set_value(3)
                self._widgets['weight_rx'].set_value(4)
                self._widgets['weight_tl'].set_value(6)
            elif preset == "medium":
                self._widgets['threshold'].set_value(5)
                self._widgets['bonus_tr'].set_value(4)
                self._widgets['weight_kw'].set_value(2)
                self._widgets['weight_rx'].set_value(3)
                self._widgets['weight_tl'].set_value(5)
            elif preset == "low":
                self._widgets['threshold'].set_value(8)
                self._widgets['bonus_tr'].set_value(5)
                self._widgets['weight_kw'].set_value(1)
                self._widgets['weight_rx'].set_value(2)
                self._widgets['weight_tl'].set_value(3)
            self._preset_changing = False

        def on_spin_changed(spin):
            if not getattr(self, '_preset_changing', False) and preset_combo.get_active_id() != "custom":
                self._preset_changing = True
                preset_combo.set_active_id("custom")
                self._preset_changing = False

        preset_combo.connect("changed", on_preset_changed)
        for k in ['threshold', 'weight_kw', 'weight_rx', 'weight_tl', 'bonus_tr']:
            if k in self._widgets:
                self._widgets[k].connect("value-changed", on_spin_changed)

        main_box.show_all(); return main_box

    def load_ui_from_config(self, ui):
        c = self.get_config()
        self._preset_changing = True
        for k in ['threshold', 'weight_kw', 'weight_rx', 'weight_tl', 'bonus_tr']:
            w = self._widgets.get(k) or self._find_w(ui, k)
            if w: w.set_value(float(c.get(k, plugin_defaults[k])))
        for k, n in [('whitelist', 'wl'), ('trusted', 'tr'), ('keywords', 'kw'), ('regex', 'rx'), ('tlds', 'tl')]:
            tv = self._widgets.get(n) or self._find_w(ui, n)
            if tv: tv.get_buffer().set_text(str(c.get(k, plugin_defaults.get(k, ''))))
            
        preset_combo = self._widgets.get('preset_combo') or self._find_w(ui, 'preset_combo')
        if preset_combo:
            t = float(c.get('threshold', plugin_defaults['threshold']))
            kw = float(c.get('weight_kw', plugin_defaults['weight_kw']))
            rx = float(c.get('weight_rx', plugin_defaults['weight_rx']))
            tl = float(c.get('weight_tl', plugin_defaults['weight_tl']))
            tr = float(c.get('bonus_tr', plugin_defaults['bonus_tr']))
            if (t, tr, kw, rx, tl) == (3, 2, 3, 4, 6):
                preset_combo.set_active_id("high")
            elif (t, tr, kw, rx, tl) == (5, 4, 2, 3, 5):
                preset_combo.set_active_id("medium")
            elif (t, tr, kw, rx, tl) == (8, 5, 1, 2, 3):
                preset_combo.set_active_id("low")
            else:
                preset_combo.set_active_id("custom")
        self._preset_changing = False

    def save_ui_to_config(self, ui):
        c = self.get_config()
        for k in ['threshold', 'weight_kw', 'weight_rx', 'weight_tl', 'bonus_tr']:
            w = self._widgets.get(k) or self._find_w(ui, k)
            if w: c[k] = int(w.get_value())
        for k, n in [('whitelist', 'wl'), ('trusted', 'tr'), ('keywords', 'kw'), ('regex', 'rx'), ('tlds', 'tl')]:
            tv = self._widgets.get(n) or self._find_w(ui, n)
            if tv:
                b = tv.get_buffer()
                raw = b.get_text(b.get_start_iter(), b.get_end_iter(), False)
                items = list(dict.fromkeys(self._split_smart(raw)))
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
        sender = getattr(mail, 'sender', None) or ('', '')
        addr = (sender[1] or '').lower()
        if self._whitelist_re and self._whitelist_re.search(addr): return False
        
        score = 0
        if addr in self._trusted_emails:
            score -= (self._bonus_tr * 2)
        else:
            domain = addr.rsplit('@', 1)[-1] if '@' in addr else addr
            if domain in self._trusted_domains:
                score -= self._bonus_tr

        subj = getattr(mail, 'subject', None) or ''
        body = getattr(mail, 'content', None) or getattr(mail, 'snippet', None) or ''

        if self._kw_super_re:
            if self._kw_super_re.search(subj): score += (self._weight_kw * 2)
            if score >= self._threshold: return True
            if self._kw_super_re.search(body): score += self._weight_kw
            if score >= self._threshold: return True

        if self._tl_set:
            tld = addr.split('.')[-1]
            if tld in self._tl_set: score += self._weight_tl
            if score >= self._threshold: return True

        if self._rx_res:
            name = sender[0] or ''
            for r in self._rx_res:
                if r.search(name) or r.search(subj) or r.search(body): score += self._weight_rx
                if score >= self._threshold: return True
            
        return score >= self._threshold
