Advanced Spam Filter for Mailnag (v4.0)

A high-performance, granular weighted spam filter for Mailnag featuring cumulative scoring, optimized regex aggregation, and a fully customizable configuration GUI.
Features

    Fully Granular Scoring: Every detection category has its own adjustable weight. You can fine-tune exactly how many "Spam Points" a match is worth.

    Adjustable Global Threshold: Set the total score required to filter an email. This allows for anything from aggressive filtering to a "safety net" approach.

    Intelligent Whitelisting: Supports exact email addresses and domain-wide filters (e.g., @company.com). Protected against spoofing via strict regex anchoring ($).

    Smart-Split Logic: Automatically handles patterns entered line-by-line or comma-separated. It intelligently preserves regex quantifiers like {1,3}.

    Automated Hygiene: Upon saving, all lists are trimmed, deduplicated, and sorted alphabetically to keep your configuration file clean and readable.

    Performance Optimized: Category-specific regex engines ensure fast processing with minimal system impact.

Scoring & Configuration

The filter calculates a score for every incoming mail by adding up the weights of all matched categories. If the total score reaches or exceeds your Global Threshold, the mail is filtered.
Adjustable Weights (GUI)
Category	Default Weight	Description
Keywords	2	Simple strings/phrases in sender name, subject, or body.
Regex	3	Complex patterns (e.g., tracking IDs, dynamic hashes).
Blocked TLDs	5	Triggered if the sender's domain matches a blocked TLD.

Example Strategy:

    Set Threshold to 10 and TLD Weight to 10 to block suspicious TLDs instantly.

    Set Threshold to 5 and Keyword Weight to 1 to require multiple keyword matches before a mail is flagged as spam.

Installation

    Copy spamfilterplugin.py to your Mailnag plugin directory:

        System-wide: /usr/lib/python3.14/site-packages/Mailnag/plugins/

        Local: ~/.local/share/mailnag/plugins/

    Open Mailnag Configuration and enable "Advanced Spam Filter".

    Go to the plugin settings tab to configure your custom weights, threshold, and patterns.
