# Implementation steps

1. **Request intake (implemented):** Parse exactly one matter number and one of the five supported categories from an email. Return a clarification for missing or ambiguous requests. Keep quoted prior replies out of scope.
2. **Browser proof of concept (implemented, unverified live):** `scripts/retrieve-uarb.mjs` attempts matter search, exact matter confirmation, visits five tabs, reads visible “Found Count” values, and downloads one “Go Get It” file. The live DOM, count semantics, and download event behavior still need verification when the site responds.
3. **Core retrieval (partially implemented):** Deterministic first-ten selection, basic local file checks, and safe ZIP names are implemented in `senpilot/archive.py`. Pagination and real browser downloads still require site access.
4. **Email workflow (partially implemented):** `senpilot/mail.py` can fetch unseen plain-text requests over IMAP without marking them read and send a prepared reply over SMTP/TLS. `senpilot/worker.py` connects intake, a retrieval callback, ZIP creation, reply composition, and sending. It marks an inbound message read after a successful send. The real UARB retrieval callback and a live mailbox test are still missing.
5. **Hardening and acceptance:** Add bounded retries, structured logs, cleanup, and live runs across valid, empty, invalid, and partial-failure cases.

The UARB endpoint timed out from this environment on 2026-09-20, so live browser selectors and counts remain unverified. Do not treat screenshot labels in `DESIGN.md` as verified selectors.

Run all local tests with `python3 -m unittest discover -s tests -v`. When the site is reachable, run `npm run probe:uarb` to capture the entry page text and screenshot before implementing browser locators. The probe reports the last browser URL and attempts a diagnostic screenshot on failure. Set `UARB_TIMEOUT_MS=60000` to allow a slower connection more time.

Run the browser proof of concept with `npm run inspect:uarb -- M12205 'Other Documents'`. It writes one downloaded file under `artifacts/M12205/` and prints observed “Found Count” values. Do not use those values in replies until their meaning and tab transitions have been verified against the live site.

The earlier SQLite job ledger, ZIP manifest/hash data, and offline fixture harness were removed to keep the assessment implementation focused on the requested behavior. `DESIGN.md` still describes those as possible production extensions, not implemented features.

For a provider that supports IMAP and SMTP with password authentication, set `SENPILOT_IMAP_HOST`, `SENPILOT_SMTP_HOST`, `SENPILOT_EMAIL_USER`, and `SENPILOT_EMAIL_PASSWORD`. Ports default to 993 and 465, with optional `SENPILOT_IMAP_PORT` and `SENPILOT_SMTP_PORT`. Credentials are read when constructing the adapters and are not stored in this repository.
