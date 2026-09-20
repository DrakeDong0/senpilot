"""Poll a configured mailbox and process UARB document requests."""

import argparse
import os

from .mail import mailbox_from_env, sender_from_env
from .uarb import retrieve_uarb
from .worker import run_forever, run_once


def main() -> None:
    parser = argparse.ArgumentParser(description="Process document requests from a dedicated mailbox")
    parser.add_argument("--once", action="store_true", help="Process currently unseen messages once and exit")
    parser.add_argument("--poll-seconds", type=float, default=60, help="Polling interval (default: 60)")
    args = parser.parse_args()
    agent_address = os.environ["SENPILOT_AGENT_ADDRESS"]
    mailbox, sender = mailbox_from_env(), sender_from_env()
    if args.once:
        count = run_once(mailbox, sender, retrieve_uarb, agent_address)
        print(f"Processed {count} message(s)")
        return
    try:
        run_forever(mailbox, sender, retrieve_uarb, agent_address, args.poll_seconds)
    except KeyboardInterrupt:
        print("Stopped")


if __name__ == "__main__":
    main()
