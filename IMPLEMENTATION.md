# Implementation steps

1. **Request intake (implemented):** Parse exactly one matter number and one of the five supported categories from an email. Return a clarification for missing or ambiguous requests. Keep quoted prior replies out of scope.
2. **Browser retrieval (implemented, unverified live):** `scripts/retrieve-uarb.mjs` attempts matter search, five tab counts using “Found Count” or complete pagination, and up to ten “Go Get It” downloads. It restarts the matter after counting so selection begins on the first page. It emits a JSON result with each count method. Live DOM, count semantics, metadata labels, pagination controls, and download behavior still need verification when the site responds.
3. **Core retrieval (implemented locally):** `senpilot/uarb.py` runs the browser script and checks the matter, category, counts, row count, and downloaded file paths before passing the result to the worker. `senpilot/archive.py` applies basic file checks and creates the ZIP.
4. **Email workflow (implemented locally):** `senpilot/mail.py` fetches unseen requests over IMAP and sends replies over SMTP/TLS. `senpilot/worker.py` connects intake, UARB retrieval, ZIP creation, reply composition, and sending. It sends a factual failure reply if retrieval cannot complete. `python3 -m senpilot.run` is the one-shot entry point. No live mailbox or UARB run has been completed.
5. **Hardening and acceptance:** Add bounded retries, structured logs, cleanup, and live runs across valid, empty, invalid, and partial-failure cases.

The UARB endpoint timed out from this environment on 2026-09-20, so live browser selectors and counts remain unverified. Do not treat screenshot labels in `DESIGN.md` as verified selectors.

Run all local tests with `python3 -m unittest discover -s tests -v`. When the site is reachable, run `npm run probe:uarb` to capture the entry page text and screenshot before implementing browser locators. The probe reports the last browser URL and attempts a diagnostic screenshot on failure. Set `UARB_TIMEOUT_MS=60000` to allow a slower connection more time.

Run the browser proof of concept with `npm run inspect:uarb -- M12205 'Other Documents'`. It writes up to ten downloaded files under `artifacts/M12205/` and prints a JSON result. The browser behavior needs a live acceptance check before relying on its counts and metadata in replies.

The earlier SQLite job ledger, ZIP manifest/hash data, and offline fixture harness were removed to keep the assessment implementation focused on the requested behavior. `DESIGN.md` still describes those as possible production extensions, not implemented features.

For a provider that supports IMAP and SMTP with password authentication, set `SENPILOT_IMAP_HOST`, `SENPILOT_SMTP_HOST`, `SENPILOT_EMAIL_USER`, `SENPILOT_EMAIL_PASSWORD`, and `SENPILOT_AGENT_ADDRESS`. Ports default to 993 and 465, with optional `SENPILOT_IMAP_PORT` and `SENPILOT_SMTP_PORT`. Credentials are read when constructing the adapters and are not stored in this repository. Run `python3 -m senpilot.run` for one inbox pass after the browser selectors and mailbox settings have been verified.
