# Advanced Spam Filter for Mailnag

An enhanced, rule-based spam filtering plugin for **Mailnag**. It allows you to suppress unwanted email notifications using Keywords, Regular Expressions (Regex), and Top-Level Domains (TLDs), while maintaining a priority Whitelist.

## ✨ Features

### Four-Layer Filtering
* **Whitelist:** Priority list to always allow specific senders or domains (e.g., `boss@company.com` or `@trusted.de`).
* **Keywords:** Simple comma-separated list of banned words (e.g., `viagra`, `casino`).
* **Regex Patterns:** High-level pattern matching for complex spam (e.g., tracking IDs, "Urgent" notices).
* **TLD Blocker:** Block entire domain endings like `.xyz`, `.top`, or `.biz`.

### Technical Highlights
* **Deep Scan:** Filters are applied to the sender's name, email address, subject line, and the message snippet.
* **Smart-Split Logic:** Handles complex Regex patterns (e.g., `{4,10}`) correctly without breaking at commas.
* **Integrated Validation:** The GUI highlights invalid Regex patterns in **red**, preventing plugin crashes during runtime.
* **Privacy-Focused:** Operates entirely locally; no data leaves your machine.

---

## 🚀 Installation

1. Copy the `spamfilter.py` file to your Mailnag plugins directory:
   * **Local:** `~/.local/share/mailnag/plugins/`
   * **System-wide:** `/usr/lib/python3/dist-packages/Mailnag/plugins/`
2. Restart the Mailnag daemon.
3. Enable the **Advanced Spam Filter** in the Mailnag configuration window (`mailnag-config`).

---

## ⚙️ Configuration

The plugin adds a dedicated configuration tab to the Mailnag settings GUI. 

* **Input:** Rules can be entered as a comma-separated list or one rule per line.
* **Validation:** If a Regex pattern is syntactically incorrect, the input field will provide visual feedback (red highlighting) to ensure stability.

---

### Requirements
* **Mailnag**
* **Python 3**
