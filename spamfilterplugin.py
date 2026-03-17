import gi
import re
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Pango
from Mailnag.common.plugins import Plugin, HookTypes
from Mailnag.common.i18n import _

plugin_defaults = { 
    'whitelist' : 'boss@company.com',
    'keywords' : 'newsletter, viagra, casino, bitcoin, crypto',
    'regex' : '(id|ref|nr|fall)[\\s:#-]?[a-z0-9-]{4,}',
    'tlds' : 'xyz, top, click, link'
}

class SpamfilterPlugin(Plugin):
    def __init__(self):
        self._filter_mails_hook = None
        self._filter_list = []
        self._whitelist = []

    def _split_smart(self, text):
        """ Trennt Text nach Zeilen oder Kommas, ignoriert aber Kommas in Regex-Quantifizierern. """
        if not text: return []
        # Zuerst nach Zeilen trennen
        lines = text.splitlines()
        final_patterns = []
        for line in lines:
            if ',' in line and '{' not in line:
                final_patterns.extend([p.strip() for p in line.split(',') if p.strip()])
            else:
                if line.strip(): final_patterns.append(line.strip())
        return final_patterns

    def _validate_patterns(self, config):
        errors = []
        all_p = set(self._split_smart(config.get('keywords', '')) + 
                    self._split_smart(config.get('regex', '')))
        
        for p in all_p:
            try:
                re.compile(p, re.I)
            except re.error as e:
                errors.append((p, str(e)))
        return errors

    def enable(self):
        config = self.get_config()
        wl_raw = self._split_smart(config.get('whitelist', plugin_defaults['whitelist']))
        self._whitelist = [w.lower() for w in wl_raw]
        
        self._filter_list = []
        kw_raw = self._split_smart(config.get('keywords', ''))
        rx_raw = self._split_smart(config.get('regex', ''))
        tl_raw = self._split_smart(config.get('tlds', ''))
        
        clean_patterns = set(kw_raw + rx_raw)
        for t in tl_raw:
            t = t.lstrip('.')
            if t: clean_patterns.add(f'\\.{t}\\b')

        for p in clean_patterns:
            try:
                self._filter_list.append(re.compile(p, re.I))
            except re.error:
                pass 

        def filter_mails_hook(mails):
            return [m for m in mails if not self._is_filtered(m)]
        
        self._filter_mails_hook = filter_mails_hook
        self.get_mailnag_controller().get_hooks().register_hook_func(HookTypes.FILTER_MAILS, self._filter_mails_hook)
    
    def disable(self):
        if self._filter_mails_hook:
            self.get_mailnag_controller().get_hooks().unregister_hook_func(HookTypes.FILTER_MAILS, self._filter_mails_hook)
            self._filter_mails_hook = None
    
    def get_manifest(self):
        return (_("Advanced Spam Filter"), _("Pro-filter with Smart-Split logic."), "4.0", "User")
    
    def get_default_config(self):
        return plugin_defaults

    def has_config_ui(self):
        return True

    def _create_editor(self, label_text, name):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox.pack_start(Gtk.Label(label=_(label_text), xalign=0), False, False, 0)
        sw = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_size_request(-1, 60)
        tv = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD, name=name)
        sw.add(tv)
        vbox.pack_start(sw, True, True, 0)
        return vbox
    
    def get_config_ui(self):
        config = self.get_config()
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_border_width(10)
        
        main_box.pack_start(self._create_editor('Whitelist (One per line):', 'wl'), True, True, 0)
        main_box.pack_start(self._create_editor('Keywords:', 'kw'), True, True, 0)
        main_box.pack_start(self._create_editor('Regex Patterns:', 'rx'), True, True, 0)
        main_box.pack_start(self._create_editor('Blocked TLDs:', 'tl'), True, True, 0)

        invalid = self._validate_patterns(config)
        if invalid:
            msg = _("!!! INVALID REGEX FOUND !!!\n") + \
                  '\n'.join([f"• {p}: {e}" for p, e in invalid])
            err_label = Gtk.Label(label=msg)
            err_label.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(1, 0, 0, 1))
            main_box.pack_start(err_label, False, False, 5)

        main_box.show_all()
        return main_box

    def _get_tv(self, config_ui, name):
        def find_tv(widget):
            if isinstance(widget, Gtk.TextView) and widget.get_name() == name: return widget
            if isinstance(widget, Gtk.Container):
                for c in widget.get_children():
                    res = find_tv(c)
                    if res: return res
            return None
        return find_tv(config_ui)

    def load_ui_from_config(self, config_ui):
        c = self.get_config()
        for k, n in [('whitelist', 'wl'), ('keywords', 'kw'), ('regex', 'rx'), ('tlds', 'tl')]:
            tv = self._get_tv(config_ui, n)
            if tv: tv.get_buffer().set_text(c.get(k, plugin_defaults.get(k, '')))
    
    def save_ui_to_config(self, config_ui):
        c = self.get_config()
        for k, n in [('whitelist', 'wl'), ('keywords', 'kw'), ('regex', 'rx'), ('tlds', 'tl')]:
            tv = self._get_tv(config_ui, n)
            if tv:
                b = tv.get_buffer()
                c[k] = b.get_text(b.get_start_iter(), b.get_end_iter(), False)

    def _is_filtered(self, mail):
        if not hasattr(mail, 'sender') or mail.sender is None: return False
        name, addr = mail.sender
        sender_info = f"{name} {addr}".lower()
        if any(w in sender_info for w in self._whitelist): return False
        body = getattr(mail, 'content', '') or getattr(mail, 'snippet', '') or ''
        content = f"{name} {addr} {mail.subject} {body}"
        return any(p.search(content) for p in self._filter_list)
