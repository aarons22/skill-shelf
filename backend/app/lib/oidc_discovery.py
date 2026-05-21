import httpx
from fastapi import HTTPException


def fetch_oidc_metadata(issuer_url: str) -> dict:
    """Fetch and validate an OIDC discovery document. Raises HTTPException(400) on any failure."""
    if not issuer_url:
        raise HTTPException(status_code=400, detail="OIDC provider requires an issuer URL")
    url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    try:
        r = httpx.get(url, timeout=10)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"OIDC discovery returned HTTP {e.response.status_code} at {url}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Could not reach OIDC discovery document at {url}: {e}")
    metadata = r.json()
    for key in ("authorization_endpoint", "token_endpoint"):
        if key not in metadata:
            raise HTTPException(status_code=400, detail=f"OIDC discovery document is missing '{key}'")
    return metadata
