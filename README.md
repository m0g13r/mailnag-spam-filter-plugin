Advanced Spam Filter for Mailnag

A high-performance, granular weighted spam filter for Mailnag featuring cumulative scoring, optimized regex aggregation, and a fully customizable configuration GUI.
🛠 Features

    Weighted Scoring: Every detection category has its own adjustable weight.

    Global Threshold: Set the total score required to filter an email (1-20).

    Secure Whitelisting: Supports exact addresses and domains with regex anchoring.

    Smart-Split: Handles line-breaks and commas (preserves regex quantifiers).

    Auto-Hygiene: Trims, deduplicates, and sorts all lists automatically on save.

    Fast Execution: Uses compiled, category-specific regex engines.

⚙️ Scoring & Configuration

The filter calculates a score for every incoming mail. If the total score reaches or exceeds your Global Threshold, the mail is filtered.
Category	Default Weight	Description
Keywords	2	Simple strings in sender, subject, or body.
Regex	3	Complex patterns (IDs, tracking numbers).
Blocked TLDs	5	Triggered by suspicious domains (e.g., .top).
💡 Example Strategy

    Strict: Threshold 10 + TLD Weight 10 = Block TLDs instantly.

    Vigilant: Threshold 5 + Keyword Weight 1 = Requires 5 keywords to block.

📥 Installation

    Copy spamfilterplugin.py to your Mailnag plugin directory:

        ~/.local/share/mailnag/plugins/

    Enable "Advanced Spam Filter" in Mailnag Configuration.

    Adjust your weights and patterns in the settings tab.
