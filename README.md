# Senpilot

Senpilot handles email requests for documents in the Nova Scotia Utility and Review Board (UARB) database. A request names one matter and one document category. The worker retrieves matter details and category counts, downloads up to ten files from the requested category, and replies with a summary and a ZIP of the verified downloads.

## Requirements

- Python 3.10 or newer. The Python code uses only the standard library.
- Node.js and npm, for the Playwright browser script.
- Google Chrome. The scripts default to `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`; set `CHROME_PATH` to the executable on other systems.
- Access to [the UARB database](https://uarb.novascotia.ca/fmi/webd/UARB15). The site may require a North American VPN connection.
- An IMAP/SMTP account if you want to run the email worker.

Clone or download this repository, open a terminal in its root directory, and install the Node dependency:

```sh
npm install
```

## Check website access

Check browser access to the UARB site:

```sh
npm run probe:uarb
```

The probe prints the page status and text and saves a screenshot to `artifacts/uarb-entry.png`. If the connection is slow, try `UARB_TIMEOUT_MS=60000 npm run probe:uarb`. `UARB_URL` can override the probe URL; the retrieval script uses the UARB URL in its source.

Retrieve a matter without sending email:

```sh
npm run inspect:uarb -- M12205 'Other Documents'
```

This prints a JSON result and saves up to ten files under `artifacts/M12205/`. The accepted categories are `Exhibits`, `Key Documents`, `Other Documents`, `Transcripts`, and `Recordings`. Matter numbers use the form `M` followed by five digits. The live site may label the Recordings tab `Audio Files`.

## Set up email

The email worker needs an account that supports password-based IMAP over SSL and authenticated SMTP over SSL. Create a dedicated folder or label for requests in that account; it must be accessible over IMAP and cannot be `INBOX`. The worker processes **unread messages in that folder only**. Use a separate address to send test requests so the reply goes back to the sender.

For Gmail, the server names are `imap.gmail.com` and `smtp.gmail.com`. Because this worker does not implement Google sign-in, use a [Google App Password](https://support.google.com/accounts/answer/185833?hl=en) with 2-Step Verification, if your account permits App Passwords. Do not use your regular Google password. Make sure the request label is available over IMAP. For other providers, use their IMAP and SMTP server names and an app password if required.

In the **same terminal** where you will start the worker, set the following values. Replace the example hosts, address, and folder name with yours:

```sh
export SENPILOT_IMAP_HOST='imap.example.com'
export SENPILOT_SMTP_HOST='smtp.example.com'
export SENPILOT_EMAIL_USER='agent@example.com'
export SENPILOT_AGENT_ADDRESS='agent@example.com'
export SENPILOT_IMAP_FOLDER='Senpilot'
```

Then enter the mail account's app password without putting it in a project file or shell history (bash or zsh):

```sh
printf 'Mail app password: '
read -s SENPILOT_EMAIL_PASSWORD
printf '\n'
export SENPILOT_EMAIL_PASSWORD
```

IMAP defaults to port 993 and SMTP over SSL to port 465. Set `SENPILOT_IMAP_PORT` and `SENPILOT_SMTP_PORT` only if your provider uses different SSL ports. The worker does not implement OAuth or SMTP STARTTLS.

## Test a real request

Send a **plain-text** email from a different address to the agent account, then move or label it into the configured request folder and leave it unread. For example:

```text
Subject: Documents for M12205

Please send me the Other Documents for matter M12205.
```

From the project root, process currently unread requests once:

```sh
python3 -m senpilot.run --once
```

Check the sender's inbox for a reply containing matter details, counts, and a ZIP when files were retrieved. `Processed 0 message(s)` means there were no unread messages in the configured folder. To keep polling (every 60 seconds by default), run:

```sh
python3 -m senpilot.run --poll-seconds 60
```

These commands send real email. The worker marks a request as read after sending its reply. An unexpected error stops the polling process. If login fails, check the account's app password and IMAP/SMTP access. If the browser probe fails, check Chrome's path and access to the UARB site before testing email.

## Run local tests

The local tests do not need a mailbox or live website:

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
