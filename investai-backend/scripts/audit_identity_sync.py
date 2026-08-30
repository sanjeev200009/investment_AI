"""Reconcile `public.users` against Supabase Auth and report broken identities.

WHY THIS EXISTS
---------------
After the I-02 cutover, exactly one thing decides whether someone can use the
app: does a row in `public.users` have a matching identity in Supabase Auth,
under the *same UUID*? `get_current_user` verifies the token's signature and
then looks the user up by `user_id == sub`. Both halves must line up:

  * no Supabase identity  -> `/auth/login` can never issue a token for them,
    so the account is dead no matter what the local row says
  * no local row          -> the token verifies but `get_current_user` returns
    401 "Account not provisioned", which looks like a login bug to the user

The Clerk era left both kinds behind, in two different shapes. The obvious one
is the placeholder row: the old `get_current_user` read its claims with
`jwt.get_unverified_claims()` — no signature check — and when it met an
unfamiliar `sub` it *created a user row for it*, with a synthetic
`<clerk_user_id>@clerk.local` email. The less obvious one is a row carrying a
person's real email but a locally-minted UUID and the Clerk user id parked in
`password_hash` (Clerk ids start with `user_`).

Detecting these by email pattern — which an earlier version of this script did —
finds the first kind and silently misses the second, and the second is the one
that strands a real person's account. So the check here is the authoritative
one: ask Supabase Auth who exists, and compare. The legacy markers are still
reported, but as *explanatory detail* on a row already found to be broken, never
as the test itself.

WHAT A DELETE COSTS
-------------------
Every foreign key into `users.user_id` is `ON DELETE CASCADE`: user_profiles,
risk_profiles, portfolios (and their holdings), investment_rules, notifications
and chat_sessions (and their messages) all go in one statement, silently. A
broken row is still a row someone's data is filed under. So this script reports
first, itemises what each delete would destroy, and acts only when told to.

USAGE
-----
Run from the investai-backend directory (as a module, so `app` is importable):

    python -m scripts.audit_identity_sync                    # report only
    python -m scripts.audit_identity_sync --json             # machine-readable
    python -m scripts.audit_identity_sync --offline           # skip Supabase
    python -m scripts.audit_identity_sync --delete-local-only user@example.com
    python -m scripts.audit_identity_sync --delete-local-only user@example.com --yes

`--delete-local-only` takes explicit addresses rather than deleting everything
it found: a bulk delete keyed off a live API response is the wrong default when
a transient auth outage could make every account look orphaned. It refuses any
address the audit did not independently classify as local-only.

Needs DATABASE_URL, SUPABASE_URL and SUPABASE_SERVICE_KEY (the service key is
required to list auth users; without it, use --offline for a reduced report).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict

from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal

# Legacy Clerk fingerprints. Reported as evidence on an already-broken row, not
# used to decide whether a row is broken.
CLERK_EMAIL_PATTERN = '%@clerk.local'
CLERK_ID_PREFIX = 'user_'

# Written by the two paths that legitimately create a users row today: the
# `on_auth_user_created` trigger on auth.users, and the local sync in
# /auth/register. Anything else in password_hash predates the cutover.
KNOWN_PASSWORD_HASH_MARKERS = ('supabase-managed', '[MANAGED_BY_SUPABASE]')

# Everything that cascades away with a user row. Explicit rather than reflected
# from metadata, so the report cannot silently omit a table someone later hangs
# a CASCADE foreign key off without updating this list.
DEPENDENT_TABLES = OrderedDict([
    ('user_profiles', 'user_id'),
    ('risk_profiles', 'user_id'),
    ('portfolios', 'user_id'),
    ('investment_rules', 'user_id'),
    ('notifications', 'user_id'),
    ('chat_sessions', 'user_id'),
])

# Reached only through a parent, so counting them needs a join.
INDIRECT_TABLES = OrderedDict([
    ('portfolio_holdings', (
        'portfolio_holdings h JOIN portfolios p ON h.portfolio_id = p.portfolio_id',
        'p.user_id',
    )),
    ('chat_messages', (
        'chat_messages m JOIN chat_sessions s ON m.session_id = s.session_id',
        's.user_id',
    )),
])


def _table_exists(db, table: str) -> bool:
    return bool(db.execute(
        text('SELECT to_regclass(:t) IS NOT NULL'), {'t': f'public.{table}'}
    ).scalar())


def _dependents_for(db, user_id) -> dict[str, int]:
    """Count, per table, the rows a delete of `user_id` would cascade away."""
    counts: dict[str, int] = {}
    for table, column in DEPENDENT_TABLES.items():
        if not _table_exists(db, table):
            continue                     # absent table contributes nothing
        counts[table] = db.execute(
            text(f'SELECT count(*) FROM {table} WHERE {column} = :u'),
            {'u': str(user_id)},
        ).scalar()
    for label, (from_clause, column) in INDIRECT_TABLES.items():
        if not _table_exists(db, from_clause.split()[0]):
            continue
        counts[label] = db.execute(
            text(f'SELECT count(*) FROM {from_clause} WHERE {column} = :u'),
            {'u': str(user_id)},
        ).scalar()
    return {k: v for k, v in counts.items() if v}


def fetch_auth_identities() -> dict[str, str]:
    """Return {lowercased email: user id} for every Supabase Auth user.

    Pages explicitly: `list_users` returns only the first page (50 by default),
    and treating a truncated page as the whole set would misreport every account
    beyond it as local-only — the exact false positive that must not happen in a
    script that offers to delete things.
    """
    from supabase import create_client

    s = get_settings()
    if not s.SUPABASE_SERVICE_KEY:
        raise RuntimeError(
            'SUPABASE_SERVICE_KEY is not set; cannot list auth users. '
            'Re-run with --offline for a reduced report.')

    admin = create_client(s.SUPABASE_URL, s.SUPABASE_SERVICE_KEY)
    identities: dict[str, str] = {}
    page = 1
    while True:
        res = admin.auth.admin.list_users(page=page, per_page=200)
        batch = getattr(res, 'users', res) or []
        for u in batch:
            email = (getattr(u, 'email', None) or '').lower()
            if email:
                identities[email] = str(getattr(u, 'id', ''))
        if len(batch) < 200:
            break
        page += 1
    return identities


def _legacy_markers(row) -> list[str]:
    """Human-readable evidence of where a broken row came from."""
    markers = []
    email = row['email'] or ''
    pw = row['password_hash'] or ''
    if email.endswith('@clerk.local'):
        markers.append('placeholder @clerk.local email (unverified-token era)')
    if pw.startswith(CLERK_ID_PREFIX):
        markers.append(f'Clerk user id in password_hash ({pw[:16]}...)')
    elif pw not in KNOWN_PASSWORD_HASH_MARKERS:
        markers.append(f'unrecognised password_hash ({pw[:24]!r})')
    return markers


def collect(db, *, offline: bool = False) -> dict:
    """Classify every local user against Supabase Auth."""
    local = db.execute(text("""
        SELECT user_id, email, full_name, password_hash, is_email_verified,
               created_at
        FROM users
        ORDER BY created_at
    """)).mappings().all()

    auth_error = None
    identities: dict[str, str] = {}
    if not offline:
        try:
            identities = fetch_auth_identities()
        except Exception as exc:                      # noqa: BLE001
            auth_error = f'{type(exc).__name__}: {exc}'

    matched, local_only, uuid_mismatch = [], [], []
    for row in local:
        entry = {
            'user_id': str(row['user_id']),
            'email': row['email'],
            'full_name': row['full_name'],
            'is_email_verified': bool(row['is_email_verified']),
            'created_at': str(row['created_at']) if row['created_at'] else None,
            'legacy_markers': _legacy_markers(row),
        }
        if offline or auth_error:
            entry['dependents'] = _dependents_for(db, row['user_id'])
            matched.append(entry)                    # classification unavailable
            continue

        auth_id = identities.get((row['email'] or '').lower())
        if auth_id is None:
            entry['dependents'] = _dependents_for(db, row['user_id'])
            local_only.append(entry)
        elif auth_id != str(row['user_id']):
            entry['supabase_user_id'] = auth_id
            entry['dependents'] = _dependents_for(db, row['user_id'])
            uuid_mismatch.append(entry)
        else:
            matched.append(entry)

    local_emails = {(r['email'] or '').lower() for r in local}
    auth_only = [{'email': e, 'user_id': i}
                 for e, i in identities.items() if e not in local_emails]

    return {
        'classification_available': not (offline or auth_error),
        'auth_error': auth_error,
        'total_local_users': len(local),
        'total_auth_identities': None if (offline or auth_error) else len(identities),
        'matched': matched,
        'local_only': local_only,
        'uuid_mismatch': uuid_mismatch,
        'auth_only': auth_only,
    }


def _print_entry(entry: dict, *, indent: str = '  ') -> None:
    print(f"{indent}{entry['email']}")
    print(f"{indent}  local user_id : {entry['user_id']}")
    if entry.get('supabase_user_id'):
        print(f"{indent}  supabase id   : {entry['supabase_user_id']}")
    print(f"{indent}  full_name     : {entry['full_name']!r}"
          f"   verified: {entry['is_email_verified']}")
    if entry.get('created_at'):
        print(f"{indent}  created_at    : {entry['created_at'][:19]}")
    for marker in entry.get('legacy_markers', []):
        print(f"{indent}  evidence      : {marker}")
    deps = entry.get('dependents') or {}
    if deps:
        itemised = ', '.join(f'{k}={v}' for k, v in deps.items())
        print(f"{indent}  a delete would destroy: {itemised}")
    else:
        print(f"{indent}  nothing is filed under this row")


def report(data: dict) -> int:
    """Print the audit. Returns the number of broken identities found."""
    print(f"local users        : {data['total_local_users']}")
    if data['classification_available']:
        print(f"supabase identities: {data['total_auth_identities']}")
    else:
        print('supabase identities: NOT CHECKED')
        if data['auth_error']:
            print(f"  could not reach Supabase Auth -> {data['auth_error']}")
            print('  Rows below are UNCLASSIFIED: absence of an identity could '
                  'not be established,')
            print('  and a transient outage must not be read as "these accounts '
                  'are orphaned".')
        return 0

    print(f"  in sync          : {len(data['matched'])}")
    print(f"  local-only       : {len(data['local_only'])}")
    print(f"  uuid mismatch    : {len(data['uuid_mismatch'])}")
    print(f"  auth-only        : {len(data['auth_only'])}")

    broken = len(data['local_only']) + len(data['uuid_mismatch']) + \
        len(data['auth_only'])
    if broken == 0:
        print('\nEvery local user has a matching Supabase identity. Nothing to do.')
        return 0

    if data['local_only']:
        print('\n' + '=' * 72)
        print('LOCAL-ONLY -- these accounts can never log in')
        print('=' * 72)
        print('A users row with no Supabase identity cannot be issued a token,')
        print('so /auth/login fails permanently. Re-registering the same address')
        print('does NOT recover it: handle_new_user() INSERTs into public.users')
        print('with no ON CONFLICT clause, and ix_users_email is UNIQUE, so the')
        print('trigger raises and aborts the auth.users insert -- create_user')
        print('fails with a database error. The stale local row must go first.')
        print()
        for entry in data['local_only']:
            _print_entry(entry)
            print()

    if data['uuid_mismatch']:
        print('=' * 72)
        print('UUID MISMATCH -- email matches, identity does not')
        print('=' * 72)
        print('Login succeeds at Supabase but the token\'s sub will not match the')
        print('local row, so get_current_user returns 401 "Account not')
        print('provisioned". The local user_id needs re-pointing at the Supabase')
        print('id, along with every child row referencing it.')
        print()
        for entry in data['uuid_mismatch']:
            _print_entry(entry)
            print()

    if data['auth_only']:
        print('=' * 72)
        print('AUTH-ONLY -- identity exists, local row missing')
        print('=' * 72)
        print('The local sync in /auth/register did not complete. The token will')
        print('verify and then 401 "Account not provisioned".')
        print()
        for entry in data['auth_only']:
            print(f"  {entry['email']}  (supabase id {entry['user_id']})")
        print()

    return broken


def delete_local_only(db, emails: list[str], data: dict) -> int:
    """Delete named local-only rows. Cascades handle dependents."""
    classified = {e['email'].lower(): e for e in data['local_only']}
    unknown = [e for e in emails if e.lower() not in classified]
    if unknown:
        raise RuntimeError(
            'refusing to delete address(es) the audit did not classify as '
            f'local-only: {", ".join(unknown)}')

    # Re-check inside the transaction. The report may have been read minutes
    # ago, and deleting a row whose situation has since changed is exactly the
    # surprise this script exists to prevent.
    deleted = 0
    for email in emails:
        expected_id = classified[email.lower()]['user_id']
        current = db.execute(
            text('SELECT user_id FROM users WHERE lower(email) = :e'),
            {'e': email.lower()},
        ).scalar()
        if current is None:
            raise RuntimeError(f'{email} is no longer in users; re-run the audit.')
        if str(current) != expected_id:
            raise RuntimeError(
                f'{email} now has user_id {current}, not {expected_id} as '
                'audited. Re-run the audit before deleting.')
        result = db.execute(
            text('DELETE FROM users WHERE lower(email) = :e'), {'e': email.lower()})
        deleted += result.rowcount
    db.commit()
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--offline', action='store_true',
                        help='skip the Supabase Auth lookup (reduced report)')
    parser.add_argument('--json', action='store_true',
                        help='emit the audit as JSON instead of a report')
    parser.add_argument('--delete-local-only', metavar='EMAIL', nargs='+',
                        default=[],
                        help='delete these local-only rows and everything '
                             'cascading from them')
    parser.add_argument('--yes', action='store_true',
                        help='skip the interactive confirmation')
    args = parser.parse_args()

    db = SessionLocal()
    try:
        data = collect(db, offline=args.offline)

        if args.json:
            print(json.dumps(data, indent=2, default=str))
            return 0

        report(data)

        if not args.delete_local_only:
            if data['local_only']:
                print('Report only. To remove a dead row so its address can be '
                      're-registered:')
                print('  python -m scripts.audit_identity_sync '
                      f"--delete-local-only {data['local_only'][0]['email']}")
            return 0

        targets = args.delete_local_only
        if not args.yes:
            print(f'\nDelete {len(targets)} user row(s) -- '
                  f"{', '.join(targets)} -- and everything cascading from them?")
            print('Re-read the itemised counts above first; this is not '
                  'reversible.')
            if input('Type "delete" to confirm: ').strip() != 'delete':
                print('Aborted. Nothing was changed.')
                return 1

        deleted = delete_local_only(db, targets, data)
        print(f'\nDeleted {deleted} user row(s).')
        print('That address can now be registered again from the app.')
        return 0
    except Exception as exc:                      # noqa: BLE001 - surface it plainly
        db.rollback()
        print(f'FAILED: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2
    finally:
        db.close()


if __name__ == '__main__':
    raise SystemExit(main())
