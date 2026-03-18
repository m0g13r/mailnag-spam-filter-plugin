# Advanced Spam Filter for Mailnag (v4.0)

An enhanced, granular weighted spam filtering plugin for **Mailnag**. It allows you to suppress unwanted email notifications using a scoring system based on Keywords, Regular Expressions (Regex), and Top-Level Domains (TLDs), while maintaining a priority Whitelist.

## ✨ Features

### Five-Layer Filtering
* **Whitelist:** Priority list to always allow specific senders or domains (e.g., `boss@company.com` or `@trusted.de`). **(Always Allow)**
* **Threshold:** Adjustable global score (1-20). If the total points of a mail reach this limit, it gets filtered.
* **Keywords:** Simple strings found in sender, subject, or body. **(Weight: 0-10)**
* **Regex Patterns:** High-level pattern matching for complex spam (e.g., tracking IDs). **(Weight: 0-10)**
* **TLD Blocker:** Block entire domain endings like `.xyz`, `.top`, or `.biz`. **(Weight: 0-10)**

### Technical Highlights
* **Granular Scoring:** Every category has its own adjustable weight, allowing for "Soft-Filters" or "Hard-Blocks".
* **Deep Scan:** Filters are applied to the sender's name, email address, subject line, and the message snippet.
* **Smart-Split Logic:** Handles complex Regex patterns (e.g., `{4,10}`) correctly without breaking at commas.
* **Integrated Validation:** The GUI ensures that only valid Regex patterns are processed, preventing plugin crashes during runtime.
* **Automated Hygiene:** The plugin automatically trims, deduplicates, and sorts your lists upon saving to keep the configuration clean.
* **Privacy-Focused:** Operates entirely locally; no data leaves your machine.

---

## 🚀 Installation

1. Copy the `spamfilterplugin.py` file to your Mailnag plugins directory:
   * **Local:** `~/.local/share/mailnag/plugins/`
   * **System-wide:** `/usr/lib/python3/dist-packages/Mailnag/plugins/`
2. Restart the Mailnag daemon.
3. Enable the **Advanced Spam Filter** in the Mailnag configuration window (`mailnag-config`).

---

## ⚙️ Configuration

The plugin adds a dedicated configuration tab to the Mailnag settings GUI where you can fine-tune the scoring:

### Adjustable Weights (GUI)

| Category | Default Weight | Description |
| :--- | :---: | :--- |
| **Keywords** | 2 | Simple strings in sender, subject, or body. |
| **Regex** | 3 | Complex patterns (IDs, tracking numbers). |
| **Blocked TLDs** | 5 | Triggered by suspicious domains (e.g., `.top`). |

* **Scoring:** Set the **Global Threshold** and individual **Weights** directly next to each filter list.
* **Input:** Rules can be entered as a comma-separated list or one rule per line.
* **Threshold Logic:** If `(Sum of Matches) >= Threshold`, the mail is filtered.

---

### Requirements
* **Mailnag**
* **Python 3** (3.8 or higher recommended)
