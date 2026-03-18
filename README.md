# Advanced Spam Filter for Mailnag (v4.1)

An enhanced, granular weighted spam filtering plugin for **Mailnag**. It allows you to suppress unwanted email notifications using a scoring system based on Keywords, Regular Expressions (Regex), and Top-Level Domains (TLDs), while maintaining a priority Whitelist and a "Trusted" bonus system.

## ✨ Features

### Six-Layer Filtering
* **Whitelist:** Priority list to always allow specific senders or domains. **(Bypasses all filters)**
* **Threshold:** Adjustable global score (1-20). If the total points of a mail reach this limit, it gets filtered.
* **Trusted Sources (Bonus):** Reduces the spam score for known safe contacts. Full email addresses count double the bonus value. **(Bonus: 0-20)**
* **Keywords:** Simple strings. Hits in the subject line count double the weight. **(Weight: 0-10)**
* **Regex Patterns:** Advanced pattern matching (e.g., tracking IDs) using Python regex. **(Weight: 0-10)**
* **TLD Blocker:** Block entire domain endings. Matches against the sender's address extension. **(Weight: 0-10)**

### User Interface
![Plugin Configuration Interface](config_gui.png)

### Technical Highlights
* **Dynamic Scoring:** Every category has its own adjustable weight, allowing for "Soft-Filters" or "Hard-Blocks".
* **Multipliers:** Logic-aware scoring (e.g., Subject keywords and Sender TLDs carry more weight).
* **Improved UI:** Functional tooltips explain the scoring logic directly within the configuration window.
* **Smart-Split Logic:** Handles complex Regex patterns (e.g., `{4,10}`) correctly without breaking at commas.
* **Automated Hygiene:** Automatically trims, deduplicates, and sorts your lists upon saving.
* **Privacy-Focused:** Operates entirely locally; no data leaves your machine.

---

## 🚀 Installation

1. Copy the `spamfilterplugin.py` file to your Mailnag plugins directory:
   * **Local:** `~/.local/share/mailnag/plugins/`
   * **System-wide:** `/usr/lib/python3/dist-packages/Mailnag/plugins/`
2. Restart the Mailnag daemon.
3. Enable **Advanced Spam Filter Ultra** in the Mailnag configuration window (`mailnag-config`).

---

## ⚙️ Configuration

The plugin adds a dedicated configuration tab to the Mailnag settings GUI where you can fine-tune the scoring:

### Adjustable Weights & Bonuses (GUI)

| Category | Default | Direction | Description |
| :--- | :---: | :---: | :--- |
| **Trusted** | 4 | **(-)** | Subtracts from score (Emails = 2x, Domains = 1x). |
| **Keywords** | 2 | **(+)** | Simple strings (Subject = 2x weight). |
| **Regex** | 3 | **(+)** | Complex patterns in name, subject, or body. |
| **TLDs** | 5 | **(+)** | Suspicious extensions (e.g., `.xyz`). |

* **Scoring:** Set the **Global Threshold** (Default: 5) at the top.
* **Input:** Rules can be entered as a comma-separated list or one rule per line.
* **Logic:** If `(Sum of Weights - Sum of Bonuses) >= Threshold`, the mail is filtered.

---

### Requirements
* **Mailnag**
* **Python 3** (3.8 or higher recommended)
* **Gtk 3.0**
