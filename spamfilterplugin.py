import gi
import re
import email.header
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
from Mailnag.common.plugins import Plugin, HookTypes
from Mailnag.common.i18n import _

plugin_defaults = {
    'whitelist': 'boss@company.com',
    'trusted': 'amazon.com, paypal.com, ebay.com, google.com, microsoft.com, apple.com, dhl.com',
    'keywords': 'newsletter, viagra, casino, bitcoin, crypto, unsubscribe',
    'regex': r'(id|ref|nr|fall)[\s:#-]?[a-z0-9-]{4,}',
    'tlds': 'xyz, top, click, link, biz, info',
    'infra_spam': 'deliverypro, privatedns.org, .privatedns., pagesport.com',
    'brands': 'telekom: telekom.de, telekom.com, t-online.de, t-mobile.de; vodafone: vodafone.de, vodafone.com; amazon: amazon.de, amazon.com',
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
        self._infra_spam_re = None
        self._kw_super_re = None
        self._rx_res = []
        self._tl_set = set()
        self._trusted_domains = set()
        self._trusted_emails = set()
        self._brand_impersonation = []
        self._brand_domains = {}
        self._cfg_vals = {}
        self._widgets = {}

    def _decode_header(self, text):
        if not text: return ""
        try:
            parts = email.header.decode_header(text)
            return ''.join([p.decode(e or 'utf-8', 'replace') if isinstance(p, bytes) else p for p, e in parts])
        except Exception:
            return text

    def _normalize(self, text):
        return text.lower().strip() if text else ""

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

        self._threshold  = self._cfg_vals['threshold']
        self._weight_kw  = self._cfg_vals['weight_kw']
        self._weight_rx  = self._cfg_vals['weight_rx']
        self._weight_tl  = self._cfg_vals['weight_tl']
        self._bonus_tr   = self._cfg_vals['bonus_tr']
        self._weight_kw_doubled = self._weight_kw * 2
        self._weight_rx_doubled = self._weight_rx * 2
        self._bonus_tr_doubled = self._bonus_tr * 2

        wl_raw = self._split_smart(config.get('whitelist', plugin_defaults['whitelist']))
        if wl_raw:
            wl_p = [re.escape(w.lower()) + '$' if '@' in w else f'(?:@|\\.){re.escape(w.lower())}$' for w in wl_raw]
            self._whitelist_re = re.compile('|'.join(wl_p), re.I)

        infra_raw = self._split_smart(config.get('infra_spam', plugin_defaults['infra_spam']))
        if infra_raw:
            self._infra_spam_re = re.compile('|'.join([re.escape(i) if '.' in i else i for i in infra_raw]), re.I)

        tr_raw = self._split_smart(config.get('trusted', plugin_defaults['trusted']))
        self._trusted_emails = {t.lower() for t in tr_raw if '@' in t}
        self._trusted_domains = {t.lower() for t in tr_raw if '@' not in t}

        kw_raw = self._split_smart(config.get('keywords', ''))
        if kw_raw:
            self._kw_super_re = re.compile('|'.join([re.escape(k) for k in kw_raw]), re.I | re.UNICODE)

        tl_raw = self._split_smart(config.get('tlds', ''))
        self._tl_set = {t.lower().lstrip('.') for t in tl_raw}

        rx_raw = self._split_smart(config.get('regex', ''))
        self._rx_res = []
        for p in rx_raw:
            try: self._rx_res.append(re.compile(p, re.I))
            except re.error: continue

        brands_raw = config.get('brands', plugin_defaults['brands'])
        self._brand_domains = {}
        self._brand_impersonation = []
        for item in brands_raw.split(';'):
            if ':' in item:
                b_name, b_doms = item.split(':', 1)
                b_name = b_name.strip().lower()
                self._brand_impersonation.append(b_name)
                self._brand_domains[b_name] = tuple([d.strip().lower() for d in b_doms.split(',') if d.strip()])
        self._brand_impersonation = tuple(self._brand_impersonation)

        self._filter_mails_hook = lambda mails: [m for m in mails if not self._is_filtered(m)]
        self.get_mailnag_controller().get_hooks().register_hook_func(HookTypes.FILTER_MAILS, self._filter_mails_hook)

    def disable(self):
        if self._filter_mails_hook:
            self.get_mailnag_controller().get_hooks().unregister_hook_func(HookTypes.FILTER_MAILS, self._filter_mails_hook)
            self._filter_mails_hook = None

    def get_manifest(self):
        return (_("Advanced Spam Filter Ultra"), _("Weighted scoring with priority regex and name checks."), "4.4", "User")

    def get_default_config(self): return plugin_defaults

    def has_config_ui(self): return True

    def get_config_ui(self):
        self._widgets = {}
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, border_width=10)
        
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        lbl_t = Gtk.Label(label=_("Global Spam Threshold:"), xalign=0)
        top_bar.pack_start(lbl_t, False, False, 0)
        adj_t = Gtk.Adjustment(value=5, lower=1, upper=20, step_increment=1)
        spin_t = Gtk.SpinButton(adjustment=adj_t, name='threshold')
        spin_t.set_tooltip_text(_("Limit for filtering."))
        top_bar.pack_start(spin_t, False, False, 0)
        self._widgets['threshold'] = spin_t

        preset_combo = Gtk.ComboBoxText(name='preset_combo')
        preset_combo.append("custom", _("Custom Profile"))
        preset_combo.append("high", _("High (Aggressive)"))
        preset_combo.append("medium", _("Medium (Default)"))
        preset_combo.append("low", _("Low (Relaxed)"))
        preset_combo.set_active_id("custom")
        top_bar.pack_end(preset_combo, False, False, 0)
        self._widgets['preset_combo'] = preset_combo
        
        main_box.pack_start(top_bar, False, False, 0)
        main_box.pack_start(Gtk.Separator(), False, False, 0)

        notebook = Gtk.Notebook()
        main_box.pack_start(notebook, True, True, 0)

        def add_tab(label_text):
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, border_width=10)
            notebook.append_page(vbox, Gtk.Label(label=label_text))
            return vbox

        def add_row(parent, label_text, value_name, tv_name, help_txt, def_val=0, is_bonus=False, height=80):
            row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            lbl = Gtk.Label(label=f"<b>{_(label_text)}</b>", xalign=0, use_markup=True)
            header.pack_start(lbl, True, True, 0)
            if value_name:
                header.pack_start(Gtk.Label(label=_("Bonus (-):") if is_bonus else _("Weight (+):"), xalign=1), False, False, 0)
                adj = Gtk.Adjustment(value=def_val, lower=0, upper=20, step_increment=1)
                spin = Gtk.SpinButton(adjustment=adj, name=value_name)
                header.pack_start(spin, False, False, 0)
                self._widgets[value_name] = spin
            row_box.pack_start(header, False, False, 0)
            sw = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN, height_request=height)
            tv = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD, name=tv_name)
            tv.set_tooltip_text(help_txt)
            sw.add(tv)
            row_box.pack_start(sw, True, True, 0)
            parent.pack_start(row_box, True, True, 0)
            self._widgets[tv_name] = tv

        tab_rules = add_tab(_("Scoring Rules"))
        add_row(tab_rules, "Spam Keywords", "weight_kw", "kw", _("Simple text strings."), 2)
        add_row(tab_rules, "Regex Patterns", "weight_rx", "rx", _("Advanced regular expressions."), 3)
        add_row(tab_rules, "Blocked TLDs", "weight_tl", "tl", _("e.g. xyz, top"), 5, height=50)

        tab_sources = add_tab(_("Sender Lists"))
        add_row(tab_sources, "Whitelist (Always Allow)", None, "wl", _("Bypass all filters."), height=60)
        add_row(tab_sources, "Infra Spam (Always Block)", None, "infra", _("Immediate block (No score)."), height=60)
        add_row(tab_sources, "Trusted Sources (Bonus)", "bonus_tr", "tr", _("Score reduction."), 4, True, height=60)

        tab_brands = add_tab(_("Brand Protection"))
        lbl_help = Gtk.Label(xalign=0)
        lbl_help.set_markup("<small><i>Format: Brand: domain.com, domain2.com (One per line)</i></small>")
        tab_brands.pack_start(lbl_help, False, False, 0)
        add_row(tab_brands, "Protected Brands", None, "br", _("Checks for impersonation."), height=150)

        self._preset_changing = False
        def on_preset_changed(combo):
            if self._preset_changing: return
            self._preset_changing = True
            p = combo.get_active_id()
            vals = {"high": (3,2,3,4,6), "medium": (5,4,2,3,5), "low": (8,5,1,2,3)}.get(p)
            if vals:
                for k, v in zip(['threshold','bonus_tr','weight_kw','weight_rx','weight_tl'], vals):
                    self._widgets[k].set_value(v)
            self._preset_changing = False

        def on_spin_changed(spin):
            if not self._preset_changing and preset_combo.get_active_id() != "custom":
                self._preset_changing = True
                preset_combo.set_active_id("custom")
                self._preset_changing = False

        preset_combo.connect("changed", on_preset_changed)
        for k in ['threshold', 'weight_kw', 'weight_rx', 'weight_tl', 'bonus_tr']:
            self._widgets[k].connect("value-changed", on_spin_changed)

        main_box.show_all()
        return main_box

    def load_ui_from_config(self, ui):
        c = self.get_config()
        self._preset_changing = True
        for k in ['threshold', 'weight_kw', 'weight_rx', 'weight_tl', 'bonus_tr']:
            if k in self._widgets: self._widgets[k].set_value(float(c.get(k, plugin_defaults[k])))
        for k, n in [('whitelist','wl'),('infra_spam','infra'),('trusted','tr'),('keywords','kw'),('regex','rx'),('tlds','tl'),('brands','br')]:
            if n in self._widgets:
                val = str(c.get(k, plugin_defaults.get(k, '')))
                if k == 'brands':
                    val = '\n'.join([b.strip() for b in val.split(';') if b.strip()])
                self._widgets[n].get_buffer().set_text(val)
        self._preset_changing = False

    def save_ui_to_config(self, ui):
        c = self.get_config()
        for k in ['threshold', 'weight_kw', 'weight_rx', 'weight_tl', 'bonus_tr']:
            if k in self._widgets: c[k] = int(self._widgets[k].get_value())
        for k, n in [('whitelist','wl'),('infra_spam','infra'),('trusted','tr'),('keywords','kw'),('regex','rx'),('tlds','tl'),('brands','br')]:
            if n in self._widgets:
                buf = self._widgets[n].get_buffer()
                text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()
                if k == 'brands':
                    c[k] = '; '.join([b.strip() for b in text.splitlines() if b.strip()])
                else:
                    c[k] = '\n'.join(list(dict.fromkeys(self._split_smart(text))))
                buf.set_text(c[k])

    def _is_filtered(self, mail):
        sender = getattr(mail, 'sender', None) or ('', '')
        name, addr = self._decode_header(sender[0] or '').lower(), (sender[1] or '').lower()
        if not addr: return False
        if self._whitelist_re and self._whitelist_re.search(addr): return False
        if self._infra_spam_re and self._infra_spam_re.search(addr): return True

        score, domain = 0, addr.rsplit('@', 1)[-1] if '@' in addr else addr
        if addr in self._trusted_emails: score -= self._bonus_tr_doubled
        elif domain in self._trusted_domains: score -= self._bonus_tr

        subj = self._decode_header(getattr(mail, 'subject', '') or '').lower()
        body = (getattr(mail, 'content', None) or getattr(mail, 'snippet', None) or '').lower()

        for brand in self._brand_impersonation:
            if brand in name:
                allowed = self._brand_domains.get(brand, ())
                if not any(domain == d or domain.endswith('.' + d) for d in allowed):
                    score += self._weight_rx
                break

        if self._rx_res:
            for r in self._rx_res:
                if r.search(name) or r.search(addr) or r.search(body): score += self._weight_rx
                if r.search(subj): score += self._weight_rx_doubled
                if score >= self._threshold: return True

        if self._kw_super_re:
            score += len(set(self._kw_super_re.findall(name))) * self._weight_kw
            score += len(set(self._kw_super_re.findall(subj))) * self._weight_kw_doubled
            score += len(set(self._kw_super_re.findall(body))) * self._weight_kw
            if score >= self._threshold: return True

        if self._tl_set and domain.rsplit('.', 1)[-1] in self._tl_set: score += self._weight_tl
        return score >= self._threshold
