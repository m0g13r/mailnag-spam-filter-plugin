Advanced Spam Filter for Mailnag

An enhanced, rule-based spam filtering plugin for Mailnag that allows you to block unwanted email notifications using Keywords, Regular Expressions (Regex), and Top-Level Domains (TLDs), while maintaining a safe Whitelist.
### Features

    Four-Layer Filtering:

        Whitelist: Always allow specific senders or domains (e.g., boss@company.com or @trusted.de).

        Keywords: Simple comma-separated list of banned words (e.g., viagra, casino).

        Regex Patterns: High-level pattern matching for complex spam (e.g., tracking IDs, "Urgent" notices).

        TLD Blocker: Block entire domain endings like .xyz, .top, or .biz.

    Deep Scan: Filters are applied to the sender's name, email address, subject line, and the message snippet/content.

    Smart-Split Logic: Handles complex Regex patterns (like {4,10}) correctly without breaking at the comma.

    Integrated Validation: Built-in GUI check that highlights invalid Regex patterns in red, preventing plugin crashes.

    Privacy-Focused: Operates entirely locally on your machine.

### Installation

    Copy the spamfilter.py file to your Mailnag plugins directory (usually ~/.local/share/mailnag/plugins/ or /usr/lib/python3/dist-packages/Mailnag/plugins/).

    Restart Mailnag.

    Enable the Advanced Spam Filter in the Mailnag configuration window.

### Configuration

The plugin provides a dedicated configuration tab in the Mailnag settings. You can enter rules as a comma-separated list or one rule per line for better readability.
