"""Tests for I-03: the OTP is a real gate, and reset tokens survive a restart.

Two defects, both of which only became load-bearing once I-02 made the Supabase
identity the single source of truth:

**H-4 — the OTP was decorative.** ``/auth/register`` created the Supabase user
with ``email_confirm: True``, so Supabase would accept
``sign_in_with_password`` for that account before any code was entered. The only
thing the OTP guarded was our own ``users.is_email_verified`` column, consulted
by our own ``/auth/login`` — and the anon key needed to talk to Supabase
directly is public by design and ships inside the mobile app. On top of that,
verification counted no attempts, so a six-digit code accepted unlimited
guesses.

**H-3 — reset tokens lived in a module-level dict.** Every pending reset was
lost when the process restarted, no sibling worker could see a token minted by
another, and nothing ever expired.

These run against in-memory SQLite so the suite stays hermetic — no live
database, no network. Only the two tables under test are created; the rest of
the metadata needs pgvector and Postgres types.

    python -m pytest tests/test_otp_and_reset_tokens.py -v
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.otp import OTPCode, PasswordResetToken
from app.services import otp as otp_service
from app.services.otp import (MAX_OTP_ATTEMPTS, OTP_EXPIRY_MINUTES,
                              create_otp, generate_otp, verify_otp)
from app.utils.security import (RESET_TOKEN_EXPIRY_MINUTES, _hash_token,
                                create_reset_token,
                                purge_expired_reset_tokens,
                                verify_reset_token)

EMAIL = "otp.subject@example.com"
OTHER = "someone.else@example.com"


@pytest.fixture
def db():
    """A throwaway session holding only otp_codes and password_reset_tokens."""
    engine = create_engine("sqlite://")
    OTPCode.__table__.create(engine)
    PasswordResetToken.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _record(db, email=EMAIL, purpose="register") -> OTPCode:
    return db.query(OTPCode).filter(
        OTPCode.email == email, OTPCode.purpose == purpose).first()


# ---------------------------------------------------------------------------
# code generation
# ---------------------------------------------------------------------------
def test_generated_code_is_six_digits():
    assert re.fullmatch(r"\d{6}", generate_otp())


def test_generation_does_not_use_the_mersenne_twister(monkeypatch):
    """``random`` is seedable and its internal state is recoverable from observed
    output, so codes minted with it are predictable in principle. Breaking the
    whole module proves generation does not reach for it: this fails loudly if
    anyone reverts to ``random.choices``.
    """
    import random

    def _forbidden(*_a, **_kw):
        raise AssertionError("OTP generation must not use the random module")

    for name in ("choice", "choices", "randint", "randrange", "sample"):
        monkeypatch.setattr(random, name, _forbidden)

    assert re.fullmatch(r"\d{6}", generate_otp())


def test_generation_covers_the_full_range():
    """A sanity check that nothing has narrowed the alphabet or length: 300 codes
    should not collapse onto a handful of values, and leading zeros must survive
    (they would be lost if the code were ever stored as an integer)."""
    codes = {generate_otp() for _ in range(300)}
    assert len(codes) > 250
    assert all(len(c) == 6 for c in codes)


# ---------------------------------------------------------------------------
# happy path and single use
# ---------------------------------------------------------------------------
def test_correct_code_verifies(db):
    code = create_otp(db, EMAIL, purpose="register")
    assert verify_otp(db, EMAIL, code, purpose="register") is True


def test_a_verified_code_cannot_be_reused(db):
    code = create_otp(db, EMAIL, purpose="register")
    assert verify_otp(db, EMAIL, code, purpose="register") is True
    assert verify_otp(db, EMAIL, code, purpose="register") is False


def test_code_is_scoped_to_its_purpose(db):
    """A registration code must not double as a password-reset code."""
    code = create_otp(db, EMAIL, purpose="register")
    assert verify_otp(db, EMAIL, code, purpose="reset_password") is False
    assert verify_otp(db, EMAIL, code, purpose="register") is True


def test_code_is_scoped_to_its_email(db):
    code = create_otp(db, EMAIL, purpose="register")
    assert verify_otp(db, OTHER, code, purpose="register") is False


def test_requesting_a_new_code_invalidates_the_old_one(db):
    first = create_otp(db, EMAIL, purpose="register")
    second = create_otp(db, EMAIL, purpose="register")
    assert first != second
    assert verify_otp(db, EMAIL, first, purpose="register") is False
    assert verify_otp(db, EMAIL, second, purpose="register") is True


def test_verify_with_no_code_on_file(db):
    assert verify_otp(db, EMAIL, "123456", purpose="register") is False


# ---------------------------------------------------------------------------
# H-4: attempts are bounded
# ---------------------------------------------------------------------------
def test_wrong_guess_increments_attempts(db):
    code = create_otp(db, EMAIL, purpose="register")
    wrong = "000000" if code != "000000" else "111111"

    assert verify_otp(db, EMAIL, wrong, purpose="register") is False
    assert _record(db).attempts == 1
    assert verify_otp(db, EMAIL, wrong, purpose="register") is False
    assert _record(db).attempts == 2


def test_correct_guess_after_a_few_wrong_ones_still_works(db):
    """The cap must absorb typos, not punish them."""
    code = create_otp(db, EMAIL, purpose="register")
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(MAX_OTP_ATTEMPTS - 1):
        assert verify_otp(db, EMAIL, wrong, purpose="register") is False
    assert verify_otp(db, EMAIL, code, purpose="register") is True


def test_code_is_destroyed_once_attempts_are_exhausted(db):
    """This is the core of H-4. Before, a six-digit code — 10^6 values — could be
    guessed indefinitely, and it is now the only thing between registration and a
    confirmed Supabase account."""
    code = create_otp(db, EMAIL, purpose="register")
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(MAX_OTP_ATTEMPTS):
        assert verify_otp(db, EMAIL, wrong, purpose="register") is False

    # The correct code no longer helps, and the record is gone rather than
    # sitting there with an attempts value someone could hope resets.
    assert verify_otp(db, EMAIL, code, purpose="register") is False
    assert _record(db) is None


def test_exhausting_one_email_does_not_lock_out_another(db):
    mine = create_otp(db, EMAIL, purpose="register")
    theirs = create_otp(db, OTHER, purpose="register")
    wrong = "000000" if mine != "000000" else "111111"

    for _ in range(MAX_OTP_ATTEMPTS):
        verify_otp(db, EMAIL, wrong, purpose="register")

    assert verify_otp(db, OTHER, theirs, purpose="register") is True


def test_a_fresh_code_clears_the_attempt_count(db):
    code = create_otp(db, EMAIL, purpose="register")
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(MAX_OTP_ATTEMPTS):
        verify_otp(db, EMAIL, wrong, purpose="register")

    replacement = create_otp(db, EMAIL, purpose="register")
    assert _record(db).attempts == 0
    assert verify_otp(db, EMAIL, replacement, purpose="register") is True


# ---------------------------------------------------------------------------
# expiry
# ---------------------------------------------------------------------------
def test_expired_code_is_refused_and_removed(db):
    code = create_otp(db, EMAIL, purpose="register")
    rec = _record(db)
    rec.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    assert verify_otp(db, EMAIL, code, purpose="register") is False
    assert _record(db) is None


def test_expiry_window_is_ten_minutes(db):
    create_otp(db, EMAIL, purpose="register")
    lifetime = otp_service._as_utc(_record(db).expires_at) - datetime.now(
        timezone.utc)
    assert timedelta(minutes=OTP_EXPIRY_MINUTES) - lifetime < timedelta(
        seconds=30)


def test_expiry_check_tolerates_a_naive_timestamp(db):
    """A naive value must read as a plain comparison, not raise. Postgres returns
    TIMESTAMPTZ so this cannot happen in production, but comparing naive to aware
    raises TypeError, which would turn every verification into a 500 rather than
    a refusal."""
    assert otp_service._as_utc(datetime(2020, 1, 1)) == datetime(
        2020, 1, 1, tzinfo=timezone.utc)
    aware = datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert otp_service._as_utc(aware) is aware


# ---------------------------------------------------------------------------
# the two-phase check used by /auth/verify-otp
# ---------------------------------------------------------------------------
def test_consume_false_leaves_the_code_spendable(db):
    """``/auth/verify-otp`` confirms the Supabase identity between the check and
    the spend. If Supabase is unreachable the user must be able to retry with the
    same code rather than be stranded with a spent one."""
    code = create_otp(db, EMAIL, purpose="register")

    assert verify_otp(db, EMAIL, code, purpose="register", consume=False) is True
    assert _record(db).is_used is False
    assert verify_otp(db, EMAIL, code, purpose="register") is True
    assert _record(db).is_used is True


def test_consume_false_still_counts_a_wrong_guess(db):
    """The peek must not be a free oracle — otherwise the attempt cap is
    bypassable by never asking to consume."""
    code = create_otp(db, EMAIL, purpose="register")
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(MAX_OTP_ATTEMPTS):
        assert verify_otp(db, EMAIL, wrong, purpose="register",
                          consume=False) is False
    assert verify_otp(db, EMAIL, code, purpose="register") is False


# ---------------------------------------------------------------------------
# H-3: reset tokens are durable, hashed, and single-use
# ---------------------------------------------------------------------------
def test_reset_token_round_trips(db):
    token = create_reset_token(db, EMAIL)
    assert verify_reset_token(db, token) == EMAIL


def test_reset_token_survives_a_restart(db):
    """The whole point of H-3. The old dict was process-local, so a restart
    between /verify-reset-otp and /reset-password lost the token — and with more
    than one worker, a token minted by one was invisible to the others.

    A second Session on the same database is what a different process sees.
    """
    token = create_reset_token(db, EMAIL)

    fresh = sessionmaker(bind=db.get_bind())()
    try:
        assert verify_reset_token(fresh, token) == EMAIL
    finally:
        fresh.close()


def test_raw_token_is_never_stored(db):
    """Read access to the table must yield nothing redeemable."""
    token = create_reset_token(db, EMAIL)
    stored = db.execute(select(PasswordResetToken.token_hash)).scalars().all()

    assert token not in stored
    assert stored == [_hash_token(token)]
    assert len(stored[0]) == 64


def test_reset_token_is_single_use(db):
    token = create_reset_token(db, EMAIL)
    assert verify_reset_token(db, token) == EMAIL
    assert verify_reset_token(db, token) is None


def test_expired_reset_token_is_refused(db):
    token = create_reset_token(db, EMAIL)
    row = db.query(PasswordResetToken).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    assert verify_reset_token(db, token) is None


def test_reset_token_expiry_matches_the_otp_window(db):
    """A reset token is only ever issued straight after an OTP was verified, so
    giving step two a longer life than step one would widen exposure for no
    usability gain."""
    assert RESET_TOKEN_EXPIRY_MINUTES == OTP_EXPIRY_MINUTES


def test_unknown_reset_token_is_refused(db):
    create_reset_token(db, EMAIL)
    assert verify_reset_token(db, "a-token-nobody-issued") is None


@pytest.mark.parametrize("bad", [None, ""])
def test_blank_reset_token_is_refused(db, bad):
    create_reset_token(db, EMAIL)
    assert verify_reset_token(db, bad) is None


def test_requesting_a_second_reset_invalidates_the_first(db):
    first = create_reset_token(db, EMAIL)
    second = create_reset_token(db, EMAIL)

    assert verify_reset_token(db, first) is None
    assert verify_reset_token(db, second) == EMAIL


def test_a_reset_for_one_address_does_not_affect_another(db):
    mine = create_reset_token(db, EMAIL)
    create_reset_token(db, OTHER)          # must not clear mine
    assert verify_reset_token(db, mine) == EMAIL


def test_token_only_ever_returns_its_own_email(db):
    """/reset-password compares this against the submitted email, so a token must
    not be usable to change a different account's password."""
    mine = create_reset_token(db, EMAIL)
    theirs = create_reset_token(db, OTHER)

    assert verify_reset_token(db, mine) == EMAIL
    assert verify_reset_token(db, theirs) == OTHER


def test_purge_removes_only_expired_tokens(db):
    stale = create_reset_token(db, OTHER)
    db.query(PasswordResetToken).filter(
        PasswordResetToken.email == OTHER).one().expires_at = (
            datetime.now(timezone.utc) - timedelta(minutes=1))
    db.commit()
    live = create_reset_token(db, EMAIL)

    assert purge_expired_reset_tokens(db) == 1
    assert verify_reset_token(db, stale) is None
    assert verify_reset_token(db, live) == EMAIL
