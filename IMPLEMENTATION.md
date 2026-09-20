# Implementation steps

1. **Request intake (implemented):** Parse exactly one matter number and one of the five supported categories from an email. Return a clarification for missing or ambiguous requests. Keep quoted prior replies out of scope.
2. **Browser proof of concept:** Reach the UARB site, inspect the live DOM, search and confirm a matter, verify all five full counts, and download one file. Record observed selectors and download behavior.
3. **Core retrieval (partially implemented):** Deterministic first-ten selection, local file validation, safe ZIP names, a manifest, and ZIP integrity checks are implemented in `senpilot/archive.py`. Pagination and real browser downloads still require site access.
4. **Email workflow (partially implemented):** `senpilot/reply.py` composes unsent MIME replies from verified counts, checks the ZIP manifest and attachment size, and handles empty or partial results. `senpilot/jobs.py` stores inbound message IDs and send state in SQLite so duplicate deliveries or uncertain sends cannot automatically resend. A provider adapter, inbound webhook verification, and actual sending remain to be implemented.
5. **Hardening and acceptance:** Add bounded retries, structured logs, cleanup, and live runs across valid, empty, invalid, and partial-failure cases.

The UARB endpoint timed out from this environment on 2026-09-20, so live browser selectors and counts remain unverified. Do not treat screenshot labels in `DESIGN.md` as verified selectors.

Run all local tests with `python3 -m unittest discover -s tests -v`. When the site is reachable, run `npm run probe:uarb` to capture the entry page text and screenshot before implementing browser locators. The probe reports the last browser URL and attempts a diagnostic screenshot on failure. Set `UARB_TIMEOUT_MS=60000` to allow a slower connection more time.
