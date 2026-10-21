-- finance_tool schema v1 (PostgreSQL 14 or newer)
-- Apply with:  psql "$DATABASE_URL" -f schema.sql
-- Safe to run twice: every statement uses IF NOT EXISTS or ON CONFLICT.

CREATE TABLE IF NOT EXISTS schema_version (
    version     integer PRIMARY KEY,
    applied_at  timestamptz NOT NULL DEFAULT now()
);

-- One row per bank account you own. Filled from the statement header on import.
CREATE TABLE IF NOT EXISTS accounts (
    id           bigserial PRIMARY KEY,
    bank_code    text NOT NULL,              -- e.g. 'capitron'
    account_no   text NOT NULL UNIQUE,       -- full number as printed on the statement
    holder_name  text NOT NULL,              -- as printed, e.g. 'ТЕСТ-ХЭРЭГЛЭГЧ ЖИШЭЭ'
    currency     text NOT NULL DEFAULT 'MNT',
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- One row per uploaded file. file_sha256 stops the same file being imported twice.
CREATE TABLE IF NOT EXISTS import_batches (
    id               bigserial PRIMARY KEY,
    account_id       bigint NOT NULL REFERENCES accounts(id),
    filename         text NOT NULL,
    file_sha256      text NOT NULL UNIQUE,
    period_from      date,
    period_to        date,
    opening_balance  numeric(14,2) NOT NULL,
    closing_balance  numeric(14,2) NOT NULL,
    rows_in_file     integer NOT NULL,
    rows_new         integer NOT NULL,       -- inserted by this import
    rows_skipped     integer NOT NULL,       -- already in the database (overlap)
    imported_at      timestamptz NOT NULL DEFAULT now()
);

-- Income, expense, or transfer. Transfers are excluded from income and expense totals.
CREATE TABLE IF NOT EXISTS categories (
    id          bigserial PRIMARY KEY,
    name        text NOT NULL UNIQUE,
    kind        text NOT NULL CHECK (kind IN ('income', 'expense', 'transfer')),
    sort_order  integer NOT NULL DEFAULT 0
);

-- A merchant is one payee. merchant_key is 'acct:<counterparty account>' for
-- QPay and bank transfers, and 'pos:<terminal name>' for card purchases.
-- category_id NULL means the merchant is still waiting for the user.
CREATE TABLE IF NOT EXISTS merchants (
    id            bigserial PRIMARY KEY,
    merchant_key  text NOT NULL UNIQUE,
    display_name  text NOT NULL,
    category_id   bigint REFERENCES categories(id),
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- Automatic rules for fees and similar lines. Checked before merchants.
-- match_type 'description_regex': pattern is a Python regex matched against the description.
CREATE TABLE IF NOT EXISTS rules (
    id           bigserial PRIMARY KEY,
    match_type   text NOT NULL CHECK (match_type IN ('description_regex')),
    pattern      text NOT NULL,
    category_id  bigint NOT NULL REFERENCES categories(id),
    priority     integer NOT NULL DEFAULT 100   -- lower number runs first
);

-- One row per statement line. The natural key stops overlapping imports from duplicating rows.
CREATE TABLE IF NOT EXISTS transactions (
    id                    bigserial PRIMARY KEY,
    account_id            bigint NOT NULL REFERENCES accounts(id),
    batch_id              bigint NOT NULL REFERENCES import_batches(id),
    txn_date              date NOT NULL,
    posted_at             timestamp NOT NULL,
    debit                 numeric(14,2) NOT NULL DEFAULT 0 CHECK (debit >= 0),
    credit                numeric(14,2) NOT NULL DEFAULT 0 CHECK (credit >= 0),
    balance_after         numeric(14,2) NOT NULL,
    description           text NOT NULL,
    counterparty_account  text,
    counterparty_name     text,
    merchant_id           bigint REFERENCES merchants(id),
    category_id           bigint REFERENCES categories(id),   -- NULL = unclassified
    category_source       text NOT NULL DEFAULT 'none'
                          CHECK (category_source IN ('none', 'rule', 'own', 'merchant', 'manual')),
    created_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT transactions_natural_key
        UNIQUE (account_id, posted_at, debit, credit, balance_after)
);

CREATE INDEX IF NOT EXISTS transactions_txn_date_idx ON transactions (txn_date);
CREATE INDEX IF NOT EXISTS transactions_category_idx ON transactions (category_id);
CREATE INDEX IF NOT EXISTS transactions_merchant_idx ON transactions (merchant_id);

-- ---------- Seed data (safe to re-run) ----------

INSERT INTO categories (name, kind, sort_order) VALUES
    ('Self-earned income',      'income',   1),
    ('Gifts received',          'income',   2),
    ('Donations received',      'income',   3),
    ('Other income',            'income',   4),
    ('Housing',                 'expense', 10),
    ('Utilities',               'expense', 11),
    ('Restaurant',              'expense', 12),
    ('Groceries',               'expense', 13),
    ('Transportation',          'expense', 14),
    ('Healthcare & Medical',    'expense', 15),
    ('Debt Payments',           'expense', 16),
    ('Personal Care & Grooming','expense', 17),
    ('Family & Pet Care',       'expense', 18),
    ('Entertainment & Recreation','expense', 19),
    ('Clothing & Apparel',      'expense', 20),
    ('Savings & Investments',   'expense', 21),
    ('Gifts & Donations',       'expense', 22),
    ('Bank Fees & Charges',     'expense', 23),
    ('Miscellaneous',           'expense', 24),
    ('Own transfers',           'transfer', 30)
ON CONFLICT (name) DO NOTHING;

-- Bank fee lines are matched by text. Patterns are Python regexes (re.search).
INSERT INTO rules (match_type, pattern, category_id, priority)
SELECT v.match_type, v.pattern, c.id, v.priority
FROM (VALUES
    ('description_regex', '^Мессэж мэдэгдэл шимтгэл',           10),
    ('description_regex', 'ИБ БАНК ХООРОНДЫН ГҮЙЛГЭЭНИЙ ШИМТГЭЛ', 11),
    ('description_regex', '^ДАНС ХӨТӨЛСНИЙ ШИМТГЭЛ',           12),
    ('description_regex', '^ATM .*fee',                          13),
    ('description_regex', '^К\.Б: CARD PAYMENT',                 14)
) AS v(match_type, pattern, priority)
JOIN categories c ON c.name = 'Bank Fees & Charges'
WHERE NOT EXISTS (
    SELECT 1 FROM rules r WHERE r.match_type = v.match_type AND r.pattern = v.pattern
);

INSERT INTO schema_version (version) VALUES (1) ON CONFLICT (version) DO NOTHING;
