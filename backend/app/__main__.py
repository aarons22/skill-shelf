import argparse

from sqlalchemy import insert, select, update

from app.db import get_transaction, run_migrations
from app.lib.auth import DEFAULT_ORGANIZATION_ID, MARKETPLACE_CREATOR, ORGANIZATION_ADMIN, now_ts, upsert_user
from app.lib.local_accounts import generate_temp_password, hash_password
from app.models import local_account_credentials, organization_role_grants, users


def main() -> None:
    parser = argparse.ArgumentParser(prog="skillshelf")
    sub = parser.add_subparsers(dest="command", required=True)
    reset = sub.add_parser("reset-password")
    reset.add_argument("email")
    promote = sub.add_parser("promote-user")
    promote.add_argument("email")
    promote.add_argument("role")
    create = sub.add_parser("create-user")
    create.add_argument("email")
    create.add_argument("display_name")
    args = parser.parse_args()

    run_migrations()
    if args.command == "reset-password":
        print(_reset_password(args.email))
    elif args.command == "promote-user":
        _promote_user(args.email, args.role)
        print(f"Granted {args.role} to {args.email}")
    elif args.command == "create-user":
        password = _create_user(args.email, args.display_name)
        print(f"Email: {args.email}\nTemporary password: {password}")


def _reset_password(email: str) -> str:
    password = generate_temp_password()
    now = now_ts()
    with get_transaction() as conn:
        user = conn.execute(select(users).where(users.c.email == email.lower())).mappings().one_or_none()
        if user is None:
            raise SystemExit(f"No user exists with email {email}")
        values = {"password_hash": hash_password(password), "must_change_password": 1, "last_password_change": now}
        existing = conn.execute(select(local_account_credentials.c.user_id).where(local_account_credentials.c.user_id == user["id"])).one_or_none()
        if existing is None:
            conn.execute(insert(local_account_credentials).values(user_id=user["id"], **values))
        else:
            conn.execute(update(local_account_credentials).where(local_account_credentials.c.user_id == user["id"]).values(**values))
    return password


def _promote_user(email: str, role: str) -> None:
    if role not in (ORGANIZATION_ADMIN, MARKETPLACE_CREATOR):
        raise SystemExit(f"Role must be one of: {ORGANIZATION_ADMIN}, {MARKETPLACE_CREATOR}")
    with get_transaction() as conn:
        user = conn.execute(select(users).where(users.c.email == email.lower())).mappings().one_or_none()
        if user is None:
            raise SystemExit(f"No user exists with email {email}")
        existing = conn.execute(
            select(organization_role_grants.c.role).where(
                organization_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
                organization_role_grants.c.principal_type == "user",
                organization_role_grants.c.principal_id == user["id"],
                organization_role_grants.c.role == role,
            )
        ).one_or_none()
        if existing is None:
            conn.execute(insert(organization_role_grants).values(
                organization_id=DEFAULT_ORGANIZATION_ID,
                principal_type="user",
                principal_id=user["id"],
                role=role,
                created_at=now_ts(),
            ))


def _create_user(email: str, display_name: str) -> str:
    password = generate_temp_password()
    now = now_ts()
    with get_transaction() as conn:
        existing = conn.execute(select(users.c.id).where(users.c.email == email.lower())).one_or_none()
        if existing is not None:
            raise SystemExit(f"A user already exists with email {email}")
        actor = upsert_user(conn, "local", email.lower(), email.lower(), display_name)
        conn.execute(insert(local_account_credentials).values(
            user_id=actor.user_id,
            password_hash=hash_password(password),
            must_change_password=1,
            last_password_change=now,
        ))
    return password


if __name__ == "__main__":
    main()
