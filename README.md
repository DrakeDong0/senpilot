# Senpilot

Senpilot handles email requests for documents in the Nova Scotia Utility and Review Board (UARB) database. A request names one matter and one document category. The worker retrieves matter details and category counts, downloads up to ten files from the requested category, and replies with a summary and a ZIP of the verified downloads.

## Requirements

- Python 3.10 or newer. The Python code uses only the standard library.
- Node.js and npm, for the Playwright browser script.
- Google Chrome. The scripts default to `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`; set `CHROME_PATH` to the executable on other systems.
- Access to [the UARB database](https://uarb.novascotia.ca/fmi/webd/UARB15). The site may require a North American VPN connection.
- An IMAP/SMTP account if you want to run the email worker.

From the project root, install the Node dependency:

```sh
npm install
```

## Run locally

Check browser access to the UARB site:

```sh
npm run probe:uarb
```

The probe prints the page status and text and saves a screenshot to `artifacts/uarb-entry.png`. If the connection is slow, set `UARB_TIMEOUT_MS=60000` before running it. `UARB_URL` can override the probe URL; the retrieval script uses the UARB URL in its source.

Retrieve a matter without sending email:

```sh
npm run inspect:uarb -- M12205 'Other Documents'
```

This prints a JSON result and saves up to ten files under `artifacts/M12205/`. The accepted categories are `Exhibits`, `Key Documents`, `Other Documents`, `Transcripts`, and `Recordings`. Matter numbers use the form `M` followed by five digits. The live site may label the Recordings tab `Audio Files`.

To run the email worker, create a dedicated IMAP folder for requests and set these environment variables in your shell:

```sh
export SENPILOT_IMAP_HOST='imap.example.com'
export SENPILOT_SMTP_HOST='smtp.example.com'
export SENPILOT_EMAIL_USER='agent@example.com'
export SENPILOT_EMAIL_PASSWORD='your-password'
export SENPILOT_AGENT_ADDRESS='agent@example.com'
export SENPILOT_IMAP_FOLDER='Senpilot'
```

`SENPILOT_IMAP_FOLDER` must name a folder other than `INBOX`. IMAP defaults to port 993 and SMTP over SSL to port 465. Set `SENPILOT_IMAP_PORT` and `SENPILOT_SMTP_PORT` if your provider uses different ports. The worker expects IMAP and authenticated SMTP over SSL; it does not implement OAuth or SMTP STARTTLS.

Process currently unread requests once:

```sh
python3 -m senpilot.run --once
```

Or poll the folder continuously (every 60 seconds by default):

```sh
python3 -m senpilot.run --poll-seconds 60
```

These commands send real email. The worker marks a request as read after sending its reply. An unexpected error stops the polling process.

Run the local tests with:

```sh
python3 -m unittest discover -s tests -v
```

## Technical details

- `senpilot/intake.py` reads the subject and plain-text body and requires exactly one matter number and one category. Missing or ambiguous requests get a clarification reply.
- `senpilot/mail.py` reads unread messages from the configured IMAP folder and sends MIME replies through SMTP over SSL.
- `senpilot/worker.py` coordinates intake, retrieval, archive creation, and replies. Each request gets a temporary workspace.
- `senpilot/uarb.py` runs `scripts/retrieve-uarb.mjs` as a subprocess with a ten-minute timeout. It checks the returned matter, category, counts, document rows, and download paths before passing them to the worker.
- `scripts/retrieve-uarb.mjs` uses Playwright with headless Chrome to navigate the FileMaker site, read matter metadata and counts for all five categories, and download the first ten records in the requested category. It records per-file errors in the result.
- `senpilot/archive.py` rejects missing, empty, HTML, or mismatched files before adding them to a ZIP. `senpilot/reply.py` reports the counts and download outcome. ZIP attachments are limited to 20 MiB by default.

The browser-only command keeps downloads in `artifacts/`, which Git ignores. The email worker uses a temporary directory that is removed after processing. `DESIGN.md` describes possible production extensions; `IMPLEMENTATION.md` records the current implementation and verification history.

The browser retrieval has been exercised against the live UARB site. The full email send/receive flow and partial-download failure case still need live acceptance testing with a configured mailbox.

## Improvements

- Add bounded retries for temporary UARB connection or download failures, with logs that identify the failed step.
- Add a durable job record so a restart or uncertain email send cannot cause duplicate replies.