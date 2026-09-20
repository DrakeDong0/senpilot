"""Process unseen requests once using the configured mailbox and UARB browser."""

import os

from .mail import mailbox_from_env, sender_from_env
from .uarb import retrieve_uarb
from .worker import run_once


def main() -> None:
    agent_address = os.environ["SENPILOT_AGENT_ADDRESS"]
    count = run_once(mailbox_from_env(), sender_from_env(), retrieve_uarb, agent_address)
    print(f"Processed {count} message(s)")


if __name__ == "__main__":
    main()
