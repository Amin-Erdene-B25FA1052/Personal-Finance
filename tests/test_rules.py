"""Checks automatic classification on the anonymised sample.

Run from the project folder:  pytest tests/test_rules.py -q
"""
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from finance_tool.banks.capitron import CapitronAdapter
from finance_tool.classify import classify_line, owner_key

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "fixtures" / "capitron_sample_anonymised.xlsx"
EXPECTED = json.loads((ROOT / "fixtures" / "expected_capitron_sample.json").read_text(encoding="utf-8"))


def _classified():
    st = CapitronAdapter().parse(str(FIXTURE))
    owner = owner_key(st.holder_name)
    return [(t, classify_line(t.description, t.counterparty_account, owner)) for t in st.transactions]


def test_owner_key_strips_hyphen_and_given_name():
    assert owner_key("ТЕСТ-ХЭРЭГЛЭГЧ ЖИШЭЭ") == "ТЕСТХЭРЭГЛЭГЧ"


def test_fee_lines_are_rule_classified():
    rows = _classified()
    fees = [r for _, r in rows if r.source == "rule"]
    assert len(fees) == EXPECTED["fee_lines"] == 62
    assert all(r.category_name == "Bank Fees & Charges" for r in fees)
    assert all(r.merchant_key is None for r in fees)


def test_own_transfers_are_detected():
    rows = _classified()
    own = [(t, r) for t, r in rows if r.source == "own"]
    assert len(own) == EXPECTED["own_lines"] == 11
    assert all(r.category_name == "Own transfers" for _, r in own)
    assert sum(t.debit for t, _ in own) == Decimal(EXPECTED["own_debit_total"])
    assert sum(t.credit for t, _ in own) == Decimal(EXPECTED["own_credit_total"])


def test_tuition_payment_with_your_name_in_front_is_not_own():
    # Description starts with the holder's name, but the payee is a university.
    rows = _classified()
    hit = [(t, r) for t, r in rows if t.posted_at == datetime(2026, 8, 31, 15, 26, 0)]
    assert len(hit) == 2  # the two lines of that payment share one timestamp
    debit_line = next(r for t, r in hit if t.debit == Decimal("5000000"))
    assert debit_line.source == "none"
    assert debit_line.merchant_key is not None and debit_line.merchant_key.startswith("acct:")


def test_card_purchases_are_keyed_by_terminal_name_not_acquirer_code():
    rows = _classified()
    pos = [r for _, r in rows if r.merchant_key and r.merchant_key.startswith("pos:")]
    assert len(pos) == 5
    assert all("3099002521030055" not in r.merchant_key for r in pos)
    assert any(r.merchant_key == "pos:BZD 14 KHOROO SUVDAN SONDOR KH" for r in pos)


def test_merchant_keys_count():
    rows = _classified()
    keys = {r.merchant_key for _, r in rows if r.merchant_key}
    assert len(keys) == EXPECTED["merchant_keys"] == 27
    assert sum(k.startswith("pos:") for k in keys) == EXPECTED["pos_keys"] == 5
    assert sum(k.startswith("acct:") for k in keys) == EXPECTED["acct_keys"] == 22


def test_merchant_lines_and_nothing_left_unparsed():
    rows = _classified()
    merchant_lines = [r for _, r in rows if r.merchant_key]
    unparsed = [r for _, r in rows if r.source == "none" and r.merchant_key is None]
    assert len(merchant_lines) == EXPECTED["merchant_lines"] == 34
    assert len(unparsed) == EXPECTED["unparsed_lines"] == 0


def test_every_line_gets_exactly_one_outcome():
    rows = _classified()
    assert len(rows) == EXPECTED["rows_in_file"]
    assert len(rows) == (EXPECTED["fee_lines"] + EXPECTED["own_lines"] + EXPECTED["merchant_lines"])
