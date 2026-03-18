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
        self._trusted_domains = []
        self._trusted_emails = []
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
        for k, d in [('threshold', 5), ('weight_kw', 2), ('weight_rx', 3), ('weight_tl', 5), ('bonus_tr', 4)]:
            try:
                self._cfg_vals[k] = int(config.get(k, d))
            except:
                self._cfg_vals[k] = d

        wl_raw = self._split_smart(config.get('whitelist', plugin_defaults['whitelist']))
        if wl_raw:
            wl_p = [re.escape(w.lower()) + '$' if '@' in w else f'@{re.escape(w.lower())}$' for w in wl_raw]
            self._whitelist_re = re.compile('|'.join(wl_p), re.I)

        tr_raw = self._split_smart(config.get('trusted', plugin_defaults['trusted']))
        self._trusted_emails = [t.lower() for t in tr_raw if '@' in t]
        self._trusted_domains = [t.lower() for t in tr_raw if '@' not in t]

        kw_raw = self._split_smart(config.get('keywords', ''))
        if kw_raw:
            self._kw_super_re = re.compile('|'.join([re.escape(k) for k in kw_raw]), re.I | re.UNICODE)

        tl_raw = self._split_smart(config.get('tlds', ''))
        self._tl_set = {t.lower().lstrip('.') for t in tl_raw}

        rx_raw = self._split_smart(config.get('regex', ''))
        self._rx_res = []
        for p in rx_raw:
            try: self._rx_res.append(re.compile(p, re.I | re.UNICODE))
            except: continue

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
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, border_width=10)
        
        top_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lbl_t = Gtk.Label(label=_("Global Spam Threshold:"), xalign=0)
        top_hbox.pack_start(lbl_t, False, False, 0)
        
        adj_t = Gtk.Adjustment(value=5, lower=1, upper=20, step_increment=1)
        spin_t = Gtk.SpinButton(adjustment=adj_t, name='threshold')
        spin_t.set_tooltip_text(_("Total score limit for filtering."))
        top_hbox.pack_start(spin_t, False, False, 0)
        main_box.pack_start(top_hbox, False, False, 0)

        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 5)
        grid = Gtk.Grid(column_spacing=10, row_spacing=6)
        main_box.pack_start(grid, True, True, 0)

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
            
            grid.attach(hb, 0, row * 2, 1, 1)
            sw = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN, hexpand=True, vexpand=True, height_request=60)
            tv = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD, name=tv_name)
            tv.set_tooltip_text(help_txt)
            sw.add(tv); grid.attach(sw, 0, row * 2 + 1, 1, 1)

        add_row("Whitelist:", None, "wl", 0, 
                _("Bypasses all filters."))
        add_row("Trusted Sources:", "bonus_tr", "tr", 1, 
                _("Subtracts from score. Full addresses count double, domains count single."), 4, True)
        add_row("Spam Keywords:", "weight_kw", "kw", 2, 
                _("Adds to score. Hits in the subject line count double."), 2)
        add_row("Regex Patterns:", "weight_rx", "rx", 3, 
                _("Adds to score. Advanced pattern matching for mail content."), 3)
        add_row("Blocked TLDs:", "weight_tl", "tl", 4, 
                _("Adds to score. Checked against sender address extension."), 5)

        main_box.show_all(); return main_box

    def load_ui_from_config(self, ui):
        c = self.get_config()
        for k in ['threshold', 'weight_kw', 'weight_rx', 'weight_tl', 'bonus_tr']:
            w = self._find_w(ui, k)
            if w: w.set_value(float(c.get(k, plugin_defaults[k])))
        for k, n in [('whitelist', 'wl'), ('trusted', 'tr'), ('keywords', 'kw'), ('regex', 'rx'), ('tlds', 'tl')]:
            tv = self._find_w(ui, n)
            if tv: tv.get_buffer().set_text(str(c.get(k, plugin_defaults.get(k, ''))))

    def save_ui_to_config(self, ui):
        c = self.get_config()
        for k in ['threshold', 'weight_kw', 'weight_rx', 'weight_tl', 'bonus_tr']:
            w = self._find_w(ui, k)
            if w: c[k] = int(w.get_value())
        for k, n in [('whitelist', 'wl'), ('trusted', 'tr'), ('keywords', 'kw'), ('regex', 'rx'), ('tlds', 'tl')]:
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
        bonus_base = self._cfg_vals.get('bonus_tr', 4)
        if addr in self._trusted_emails: score -= (bonus_base * 2)
        elif any(addr.endswith(d) for d in self._trusted_domains): score -= bonus_base

        if score < -10: return False

        subj = (getattr(mail, 'subject', '') or '').lower()
        body = (getattr(mail, 'content', '') or getattr(mail, 'snippet', '') or '').lower()
        threshold = self._cfg_vals.get('threshold', 5)

        if self._kw_super_re:
            w_kw = self._cfg_vals.get('weight_kw', 2)
            if self._kw_super_re.search(subj): score += (w_kw * 2)
            if score >= threshold: return True
            if self._kw_super_re.search(body): score += w_kw
            if score >= threshold: return True

        if self._tl_set:
            tld = addr.split('.')[-1]
            if tld in self._tl_set: score += (self._cfg_vals.get('weight_tl', 5) * 2)
            if score >= threshold: return True

        if self._rx_res:
            name = (getattr(mail, 'sender', ('',''))[0] or '').lower()
            content = f"{name} {subj} {body}"
            for r in self._rx_res:
                if r.search(content): score += self._cfg_vals.get('weight_rx', 3)
                if score >= threshold: return True
            
        return score >= threshold
