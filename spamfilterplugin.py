import gi
import re
import email.header
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk          # Gdk removed — was imported but never used (BUG #5)
from Mailnag.common.plugins import Plugin, HookTypes
from Mailnag.common.i18n import _

# OPT: pre-compile the comma-guard used in _split_smart so it is not
#      recompiled on every call.
_BRACE_COMMA_RE = re.compile(r'\{[^}]*,[^}]*\}')

# Maximum number of characters scanned in the email body.
# Avoids hanging the UI thread on multi-megabyte HTML newsletters. (OPT)
_BODY_SCAN_LIMIT = 20_000

# FIX #5: Added German phishing vocabulary (warnung, konto, gesperrt, dringend…)
# FIX #6: Added bulk-mailer numeric address pattern to regex defaults
# FIX #1: Added t-mobile as its own brand entry
plugin_defaults = {
    'whitelist': 'boss@company.com',
    'trusted': 'amazon.com, paypal.com, ebay.com, google.com, microsoft.com, apple.com, dhl.com',
    'keywords': (
        'newsletter, viagra, casino, bitcoin, crypto, unsubscribe, '
        'warnung, konto, gesperrt, dringend, verifizieren, bestaetigen, '
        'verify, account suspended, click here, act now, limited time'
    ),
    # BUG #1 FIX: raw-string concatenation produced a literal backslash-n
    # (r'...\n' r'...') so both patterns were merged into one regex that
    # required a real newline in the scanned text — the bulk-mailer pattern
    # never fired. Each pattern must be on its own line in a regular string.
    'regex': (
        '(id|ref|nr|fall)[\\s:#-]?[a-z0-9-]{4,}\n'
        'newsletter\\.\\d{5,}'
    ),
    'tlds': 'xyz, top, click, link, biz, info',
    'infra_spam': 'deliverypro, privatedns.org, .privatedns., pagesport.com, engineproperty.com, green-alien.net',
    # FIX #1: t-mobile added as separate brand; t-mobile.com/de map to legitimate domains
    'brands': (
        'telekom: telekom.de, telekom.com, t-online.de, t-mobile.de; '
        't-mobile: t-mobile.de, t-mobile.com, t-online.de, telekom.de; '
        'vodafone: vodafone.de, vodafone.com; '
        'amazon: amazon.de, amazon.com; '
        'paypal: paypal.de, paypal.com; '
        'dhl: dhl.de, dhl.com'
    ),
    'threshold': 5,
    'weight_kw': 2,
    'weight_rx': 3,
    'weight_tl': 5,
    'bonus_tr': 4
}


class SpamfilterPlugin(Plugin):
    def __init__(self):
        self._filter_mails_hook  = None
        self._whitelist_re       = None
        self._infra_spam_re      = None
        self._kw_super_re        = None
        self._brand_name_re      = None   # OPT: compiled alternation for brand lookup
        self._rx_res             = []
        self._tl_set             = set()
        self._trusted_domains    = set()
        self._trusted_emails     = set()
        self._brand_impersonation = []
        self._brand_domains      = {}
        self._cfg_vals           = {}
        self._widgets            = {}
        # BUG #4 FIX: initialise here so load_ui_from_config cannot raise
        # AttributeError if called before get_config_ui.
        self._preset_changing    = False

    def _decode_header(self, text):
        """Decode a possibly RFC 2047-encoded header value.

        BUG #2 FIX: the previous implementation joined decoded parts with ''
        which fused adjacent words when a plain-text part followed an encoded
        word without an explicit space (e.g. '=?utf-8?q?Dringend=3A?=Ihr'
        became 'Dringend:Ihr').  email.header.make_header() follows RFC 2047
        whitespace rules correctly.
        """
        if not text:
            return ""
        try:
            return str(email.header.make_header(email.header.decode_header(text)))
        except Exception:
            return str(text)

    # FIX #7: _normalize was dead code — now actually used in _is_filtered
    def _normalize(self, text):
        return text.lower().strip() if text else ""

    def _split_smart(self, text):
        """Split a config value into individual tokens / patterns.

        Comma-separated simple lists are exploded; lines that look like regex
        patterns (containing a quantifier brace with a comma, e.g. {4,})
        are kept intact.  The guard regex is a module-level constant so it is
        not recompiled on every call (OPT).
        """
        if not text:
            return []
        lines = text.splitlines()
        final_patterns = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if ',' in line and not _BRACE_COMMA_RE.search(line):
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

        self._threshold         = self._cfg_vals['threshold']
        self._weight_kw         = self._cfg_vals['weight_kw']
        self._weight_rx         = self._cfg_vals['weight_rx']
        self._weight_tl         = self._cfg_vals['weight_tl']
        self._bonus_tr          = self._cfg_vals['bonus_tr']
        self._weight_kw_doubled = self._weight_kw * 2
        self._weight_rx_doubled = self._weight_rx * 2
        self._bonus_tr_doubled  = self._bonus_tr * 2

        wl_raw = self._split_smart(config.get('whitelist', plugin_defaults['whitelist']))
        if wl_raw:
            wl_p = [
                re.escape(w.lower()) + '$' if '@' in w
                else f'(?:@|\\.){re.escape(w.lower())}$'
                for w in wl_raw
            ]
            self._whitelist_re = re.compile('|'.join(wl_p), re.I)

        infra_raw = self._split_smart(config.get('infra_spam', plugin_defaults['infra_spam']))
        if infra_raw:
            self._infra_spam_re = re.compile(
                '|'.join([re.escape(i) if '.' in i else i for i in infra_raw]), re.I
            )

        tr_raw = self._split_smart(config.get('trusted', plugin_defaults['trusted']))
        self._trusted_emails  = {t.lower() for t in tr_raw if '@' in t}
        self._trusted_domains = {t.lower() for t in tr_raw if '@' not in t}

        # BUG #3 FIX: use plugin_defaults[k] as the fallback, not ''.
        # With '' as fallback, a fresh install silently drops all built-in
        # keywords, TLDs, and regex patterns.
        kw_raw = self._split_smart(config.get('keywords', plugin_defaults['keywords']))
        if kw_raw:
            self._kw_super_re = re.compile(
                '|'.join([re.escape(k) for k in kw_raw]), re.I | re.UNICODE
            )

        tl_raw = self._split_smart(config.get('tlds', plugin_defaults['tlds']))
        self._tl_set = {t.lower().lstrip('.') for t in tl_raw}

        rx_raw = self._split_smart(config.get('regex', plugin_defaults['regex']))
        self._rx_res = []
        for p in rx_raw:
            try:
                self._rx_res.append(re.compile(p, re.I))
            except re.error:
                continue

        brands_raw = config.get('brands', plugin_defaults['brands'])
        self._brand_domains = {}
        self._brand_impersonation = []
        for item in brands_raw.split(';'):
            if ':' in item:
                b_name, b_doms = item.split(':', 1)
                b_name = b_name.strip().lower()
                self._brand_impersonation.append(b_name)
                self._brand_domains[b_name] = tuple(
                    d.strip().lower() for d in b_doms.split(',') if d.strip()
                )
        self._brand_impersonation = tuple(self._brand_impersonation)

        # OPT: build a single compiled alternation so brand-name detection is
        # a single regex search rather than a Python 'in' loop per brand.
        if self._brand_impersonation:
            self._brand_name_re = re.compile(
                '|'.join(re.escape(b) for b in self._brand_impersonation), re.I
            )
        else:
            self._brand_name_re = None

        self._filter_mails_hook = lambda mails: [m for m in mails if not self._is_filtered(m)]
        self.get_mailnag_controller().get_hooks().register_hook_func(
            HookTypes.FILTER_MAILS, self._filter_mails_hook
        )

    def disable(self):
        if self._filter_mails_hook:
            self.get_mailnag_controller().get_hooks().unregister_hook_func(
                HookTypes.FILTER_MAILS, self._filter_mails_hook
            )
            self._filter_mails_hook = None

    def get_manifest(self):
        return (
            _("Advanced Spam Filter Ultra"),
            _("Weighted scoring with priority regex and name checks."),
            "4.5",
            "User"
        )

    def get_default_config(self):
        return plugin_defaults

    def has_config_ui(self):
        return True

    def get_config_ui(self):
        self._widgets = {}
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, border_width=10)

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        lbl_t = Gtk.Label(label=_("Global Spam Threshold:"), xalign=0)
        top_bar.pack_start(lbl_t, False, False, 0)
        adj_t = Gtk.Adjustment(value=5, lower=1, upper=20, step_increment=1)
        spin_t = Gtk.SpinButton(adjustment=adj_t, name='threshold')
        spin_t.set_tooltip_text(
            _("Limit for blocking: If an email's total weight reaches this value, it's filtered. Lower = stricter.")
        )
        top_bar.pack_start(spin_t, False, False, 0)
        self._widgets['threshold'] = spin_t

        preset_combo = Gtk.ComboBoxText(name='preset_combo')
        preset_combo.append("custom",  _("Custom Profile"))
        preset_combo.append("high",    _("High (Aggressive)"))
        preset_combo.append("medium",  _("Medium (Default)"))
        preset_combo.append("low",     _("Low (Relaxed)"))
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
            header  = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            lbl = Gtk.Label(label=f"<b>{_(label_text)}</b>", xalign=0, use_markup=True)
            header.pack_start(lbl, True, True, 0)
            if value_name:
                header.pack_start(
                    Gtk.Label(label=_("Bonus (Score -):") if is_bonus else _("Weight (Score +):"), xalign=1),
                    False, False, 0
                )
                adj  = Gtk.Adjustment(value=def_val, lower=0, upper=20, step_increment=1)
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
        add_row(tab_rules, "Spam Keywords", "weight_kw", "kw",
                _("Points added per matched keyword. Addr + body = 1×, subject = 2×."), 2)
        add_row(tab_rules, "Regex Patterns", "weight_rx", "rx",
                _("Points per pattern match (name/addr/body = 1×, subject = 2×). One pattern per line."), 3)
        add_row(tab_rules, "Blocked TLDs", "weight_tl", "tl",
                _("Points added if the sender domain uses one of these TLDs (e.g. .xyz)."), 5, height=50)

        tab_sources = add_tab(_("Sender Lists"))
        add_row(tab_sources, "Whitelist (Always Allow)", None, "wl",
                _("Trusted emails/domains always accepted without scoring."), height=60)
        add_row(tab_sources, "Infra Spam (Always Block)", None, "infra",
                _("Known spammer infrastructure patterns — blocked immediately (checked in addr AND display name)."), height=60)
        add_row(tab_sources, "Trusted Sources (Bonus)", "bonus_tr", "tr",
                _("Safe senders that reduce the total spam score by this amount."), 4, True, height=60)

        tab_brands = add_tab(_("Brand Protection"))
        lbl_help = Gtk.Label(xalign=0)
        lbl_help.set_markup(
            "<small><i>Format: BrandKeyword: domain.com, domain2.com  (one brand per line; "
            "use sub-brand names as keywords, e.g. 't-mobile' separately from 'telekom')</i></small>"
        )
        lbl_help.set_line_wrap(True)
        lbl_help.set_max_width_chars(60)
        tab_brands.pack_start(lbl_help, False, False, 0)
        add_row(tab_brands, "Protected Brands", None, "br",
                _("If sender display name contains a brand keyword but the domain isn't in its allowed list, "
                  "Regex Weight is added. Check addr AND display name."), height=150)

        # BUG #4 already fixed: _preset_changing initialised in __init__,
        # so it is safe whether or not get_config_ui has been called first.
        def on_preset_changed(combo):
            if self._preset_changing:
                return
            self._preset_changing = True
            p    = combo.get_active_id()
            vals = {"high": (3, 2, 3, 4, 6), "medium": (5, 4, 2, 3, 5), "low": (8, 5, 1, 2, 3)}.get(p)
            if vals:
                for k, v in zip(['threshold', 'bonus_tr', 'weight_kw', 'weight_rx', 'weight_tl'], vals):
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
            if k in self._widgets:
                self._widgets[k].set_value(float(c.get(k, plugin_defaults[k])))
        for k, n in [('whitelist', 'wl'), ('infra_spam', 'infra'), ('trusted', 'tr'),
                     ('keywords', 'kw'), ('regex', 'rx'), ('tlds', 'tl'), ('brands', 'br')]:
            if n in self._widgets:
                val = str(c.get(k, plugin_defaults.get(k, '')))
                if k == 'brands':
                    val = '\n'.join([b.strip() for b in val.split(';') if b.strip()])
                self._widgets[n].get_buffer().set_text(val)
        self._preset_changing = False

    def save_ui_to_config(self, ui):
        c = self.get_config()
        for k in ['threshold', 'weight_kw', 'weight_rx', 'weight_tl', 'bonus_tr']:
            if k in self._widgets:
                c[k] = int(self._widgets[k].get_value())
        for k, n in [('whitelist', 'wl'), ('infra_spam', 'infra'), ('trusted', 'tr'),
                     ('keywords', 'kw'), ('regex', 'rx'), ('tlds', 'tl'), ('brands', 'br')]:
            if n in self._widgets:
                buf  = self._widgets[n].get_buffer()
                text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()
                if k == 'brands':
                    c[k] = '; '.join([b.strip() for b in text.splitlines() if b.strip()])
                else:
                    c[k] = '\n'.join(list(dict.fromkeys(self._split_smart(text))))
                buf.set_text(c[k])

    def _is_filtered(self, mail):
        sender = getattr(mail, 'sender', None) or ('', '')

        # FIX #7: use _normalize consistently instead of inline .lower().strip()
        name = self._normalize(self._decode_header(sender[0] or ''))
        addr = self._normalize(sender[1] or '')

        if not addr:
            return False

        # Whitelist — checked only against addr (intentional: display name can be spoofed)
        if self._whitelist_re and self._whitelist_re.search(addr):
            return False

        # FIX #3: Infra-spam now checked against BOTH addr and display name
        if self._infra_spam_re:
            if self._infra_spam_re.search(addr) or self._infra_spam_re.search(name):
                return True

        # BUG #6 FIX: split addr once; reuse both parts instead of calling
        # rsplit('@', 1) twice (was on lines 344 and 346).
        if '@' in addr:
            local, domain = addr.rsplit('@', 1)
        else:
            local, domain = '', addr

        score = 0
        if addr in self._trusted_emails:
            score -= self._bonus_tr_doubled
        elif domain in self._trusted_domains:
            score -= self._bonus_tr

        subj = self._normalize(self._decode_header(getattr(mail, 'subject', '') or ''))

        # OPT: truncate body to _BODY_SCAN_LIMIT characters before any regex
        # or keyword scan.  A 5 MB HTML newsletter would otherwise stall the
        # UI thread for hundreds of milliseconds per email.
        raw_body = getattr(mail, 'content', None) or getattr(mail, 'snippet', None) or ''
        body = self._normalize(raw_body[:_BODY_SCAN_LIMIT])

        # Brand impersonation — checked in display name AND local part of addr.
        # FIX #1: t-mobile now a brand; FIX #4: early-exit added after score update.
        # OPT: _brand_name_re is a pre-compiled alternation; a single search
        # call replaces iterating every brand name with Python 'in' tests.
        if self._brand_name_re:
            m = self._brand_name_re.search(name) or self._brand_name_re.search(local)
            if m:
                matched_brand = m.group(0).lower()
                allowed = self._brand_domains.get(matched_brand, ())
                if not any(domain == d or domain.endswith('.' + d) for d in allowed):
                    score += self._weight_rx
                    if score >= self._threshold:   # FIX #4
                        return True

        # Regex patterns — name, addr (full), body, subject
        if self._rx_res:
            for r in self._rx_res:
                if r.search(name) or r.search(addr) or r.search(body):
                    score += self._weight_rx
                if r.search(subj):
                    score += self._weight_rx_doubled
                if score >= self._threshold:
                    return True

        # Keyword matching — FIX #2: now also scans local part of addr
        if self._kw_super_re:
            score += len(set(self._kw_super_re.findall(name)))  * self._weight_kw
            score += len(set(self._kw_super_re.findall(local))) * self._weight_kw   # FIX #2
            score += len(set(self._kw_super_re.findall(subj)))  * self._weight_kw_doubled
            score += len(set(self._kw_super_re.findall(body)))  * self._weight_kw
            if score >= self._threshold:
                return True

        # TLD check
        if self._tl_set and domain.rsplit('.', 1)[-1] in self._tl_set:
            score += self._weight_tl

        return score >= self._threshold
