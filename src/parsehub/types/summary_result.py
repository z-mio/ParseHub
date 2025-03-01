from dataclasses import dataclass


@dataclass
class SummaryResult:
    content: str


class SummaryError(Exception):
    pass
