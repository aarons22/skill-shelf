import json
from typing import Any

from fastapi import HTTPException, status


def parse_allowlist(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def enforce(provider_row: dict[str, Any], profile: dict[str, Any], group_claims: list[str] | None = None) -> None:
    provider_type = provider_row.get("provider_type")
    allowlist = parse_allowlist(provider_row.get("allowlist_json"))
    groups = group_claims or []
    allowed = True
    if provider_type == "github":
        usernames = {str(v).lower() for v in allowlist.get("usernames", [])}
        domains = {str(v).lower().lstrip("@") for v in allowlist.get("emailDomains", [])}
        orgs = {str(v).lower() for v in allowlist.get("orgs", [])}
        if usernames or domains or orgs:
            email = str(profile.get("email", "")).lower()
            username = str(profile.get("username") or profile.get("login") or "").lower()
            user_orgs = {str(v).lower() for v in profile.get("orgs", [])}
            allowed = bool(
                (username and username in usernames)
                or (email and email.split("@")[-1] in domains)
                or (orgs and user_orgs.intersection(orgs))
            )
    elif provider_type in {"oidc", "trusted_header", "trusted_headers"}:
        allowed_groups = {str(v) for v in allowlist.get("allowedGroups", [])}
        if allowed_groups:
            allowed = bool(allowed_groups.intersection({str(v) for v in groups}))
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied — your account doesn't match this provider's allowlist. Contact your administrator.",
        )
