"""Shared data contracts for finance_tool.

Every module imports its types from here. Do not rename fields or change
types without updating the prompts that depend on them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol


class StatementError(Exception):
    """Raised when a statement file cannot be parsed or fails its own checks.

    The message must say what was wrong and where (sheet, row number),
    so the user can see it on the upload page.
    """


@dataclass(frozen=True)
class ParsedTransaction:
    txn_date: date
    posted_at: datetime
    debit: Decimal                 # money out, 0 if none; never negative
    credit: Decimal                # money in, 0 if none; never negative
    balance_after: Decimal
    description: str               # raw bank text, trimmed, never edited
    counterparty_account: str | None
    counterparty_name: str | None


@dataclass
class ParsedStatement:
    bank_code: str                 # e.g. 'capitron'
    account_no: str
    holder_name: str
    period_from: date
    period_to: date
    opening_balance: Decimal
    closing_balance: Decimal
    transactions: list[ParsedTransaction] = field(default_factory=list)  # oldest first
    file_debit_total: Decimal | None = None    # from the bank's totals row, if present
    file_credit_total: Decimal | None = None


class BankAdapter(Protocol):
    """One adapter per bank. Adapters only read files. They never touch the database."""

    code: str                      # unique, lowercase, e.g. 'capitron'

    def detect(self, path: str) -> bool:
        """Return True if this file looks like this bank's statement."""
        ...

    def parse(self, path: str) -> ParsedStatement:
        """Return every line in the file, oldest first. Raise StatementError on any failed check."""
        ...


@dataclass(frozen=True)
class ClassifyResult:
    source: Literal["rule", "own", "merchant", "manual", "none"]
    category_name: str | None      # None means waiting for the user
    merchant_key: str | None       # 'acct:<account>' or 'pos:<name>', else None
    merchant_name: str | None
