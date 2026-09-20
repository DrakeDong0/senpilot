"""Conservative parsing of one matter and one document category from email."""

from dataclasses import dataclass
import re


CATEGORIES = (
    "Exhibits",
    "Key Documents",
    "Other Documents",
    "Transcripts",
    "Recordings",
)

_MATTER = re.compile(r"(?<![A-Za-z0-9])M[0-9]{5}(?![A-Za-z0-9])", re.I)
_CATEGORY = re.compile(
    r"(?<![A-Za-z])(?:key\s+documents?|other\s+documents?|exhibits?|transcripts?|recordings?)(?![A-Za-z])",
    re.I,
)
_ALIASES = {
    "exhibit": "Exhibits",
    "exhibits": "Exhibits",
    "key document": "Key Documents",
    "key documents": "Key Documents",
    "other document": "Other Documents",
    "other documents": "Other Documents",
    "transcript": "Transcripts",
    "transcripts": "Transcripts",
    "recording": "Recordings",
    "recordings": "Recordings",
}


@dataclass(frozen=True)
class Request:
    matter_number: str
    requested_type: str


class ClarificationNeeded(ValueError):
    """The message does not identify exactly one matter and category."""


def _current_message(body: str) -> str:
    """Ignore conventional quoted replies and forwarded-message headers."""
    kept = []
    for line in body.splitlines():
        stripped = line.strip()
        if (stripped.startswith(">") or
                re.match(r"^-+\s*(original message|forwarded message)\s*-+", stripped, re.I) or
                re.match(r"^On .+ wrote:$", stripped, re.I)):
            break
        kept.append(line)
    return "\n".join(kept)


def parse_request(subject: str, body: str) -> Request:
    """Parse a request or require clarification; never guess missing values."""
    text = f"{subject}\n{_current_message(body)}"
    matters = {match.upper() for match in _MATTER.findall(text)}
    categories = {
        _ALIASES[re.sub(r"\s+", " ", match.lower())]
        for match in _CATEGORY.findall(text)
    }
    if len(matters) != 1 or len(categories) != 1:
        raise ClarificationNeeded(
            "Please specify one matter number (M followed by five digits) "
            "and one document type: " + ", ".join(CATEGORIES) + "."
        )
    return Request(matter_number=next(iter(matters)), requested_type=next(iter(categories)))
