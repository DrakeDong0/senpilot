# Implementation steps

1. **Request intake (implemented):** Parse exactly one matter number and one of the five supported categories from an email. Return a clarification for missing or ambiguous requests. Keep quoted prior replies out of scope.
2. **Browser proof of concept:** Reach the UARB site, inspect the live DOM, search and confirm a matter, verify all five full counts, and download one file. Record observed selectors and download behavior.
3. **Core retrieval:** Add pagination, deterministic first-ten selection, per-file validation, safe ZIP names, manifest, and ZIP integrity checks.
4. **Email workflow:** Add a provider adapter, durable deduplication and job states, factual reply templates, attachment size checks, and sending.
5. **Hardening and acceptance:** Add bounded retries, structured logs, cleanup, and live runs across valid, empty, invalid, and partial-failure cases.

The UARB endpoint timed out from this environment on 2026-09-20, so live browser selectors and counts remain unverified. Do not treat screenshot labels in `DESIGN.md` as verified selectors.

Run the intake tests with `python3 -m unittest discover -s tests -v`. When the site is reachable, run `npm run probe:uarb` to capture the entry page text and screenshot before implementing browser locators.
