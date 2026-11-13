"""Verified caller identity from the API Gateway JWT authorizer.

Authentication (signature, expiry, issuer, audience) happens in the gateway.
This module only *reads* the already-verified claims and refuses to proceed when
they are missing, incomplete or contradictory.

Rules enforced here:

- identity is ``iss`` + ``sub`` together, never ``sub`` alone;
- the issuer must match the configured pool when configuration is present;
- the audience/client must match the configured app client when present;
- ``token_use`` must be ``id`` or ``access`` (when the claim is present);
- nothing is read from headers, query, path or body.

Configuration is fail-closed: when ``expected_issuer``/``expected_client_id``
are supplied, a mismatch is rejected. Callers decide whether absent
configuration is acceptable; the Lambda passes the deployed values.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

ALLOWED_TOKEN_USES = frozenset({"id", "access"})


class IdentityError(ValueError):
    """Rejected identity with a stable, non-leaking code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class OwnerIdentity:
    """The verified caller. ``iss`` + ``sub`` define ownership."""

    issuer: str
    subject: str
    client_id: Optional[str] = None
    token_use: Optional[str] = None
    groups: Tuple[str, ...] = ()

    @property
    def owner_key(self) -> str:
        """Stable, index-safe owner identifier (does not expose raw ``sub``)."""
        return owner_key(self.issuer, self.subject)

    def item_fields(self) -> Dict[str, str]:
        """Attributes persisted on the order item."""
        fields = {
            "ownerIssuer": self.issuer,
            "ownerSubject": self.subject,
            "ownerKey": self.owner_key,
            "actorType": "user",
            "actorId": self.subject,
        }
        if self.client_id:
            fields["ownerClientId"] = self.client_id
        return fields

    def can_read(self, item: Dict[str, Any]) -> bool:
        """Object-level check. Missing owner binding denies (legacy)."""
        stored = item.get("ownerKey")
        return bool(stored) and stored == self.owner_key


def owner_key(issuer: str, subject: str) -> str:
    normalized = _normalize_issuer(issuer)
    digest = hashlib.sha256(
        f"{normalized}\x00{subject}".encode("utf-8")
    ).hexdigest()
    return digest


def _normalize_issuer(value: str) -> str:
    return str(value).strip().rstrip("/")


def _claims(event: Dict[str, Any]) -> Dict[str, Any]:
    request_context = event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}
    jwt = authorizer.get("jwt") or {}
    claims = jwt.get("claims")
    if not isinstance(claims, dict):
        raise IdentityError(
            "missing_identity_context",
            "Request carries no verified identity context",
        )
    return claims


def _audience(claims: Dict[str, Any]) -> Tuple[str, ...]:
    audience = claims.get("aud")
    values = []
    if isinstance(audience, str) and audience:
        values.append(audience)
    elif isinstance(audience, (list, tuple)):
        values.extend(str(v) for v in audience if v)
    client_id = claims.get("client_id")
    if isinstance(client_id, str) and client_id:
        values.append(client_id)
    return tuple(dict.fromkeys(values))


def extract_identity(
    event: Dict[str, Any],
    *,
    expected_issuer: Optional[str] = None,
    expected_client_id: Optional[str] = None,
) -> OwnerIdentity:
    """Return the verified caller or raise :class:`IdentityError`."""
    if not isinstance(event, dict):
        raise IdentityError("missing_identity_context", "Invalid event")

    claims = _claims(event)

    issuer = claims.get("iss")
    if not isinstance(issuer, str) or not issuer.strip():
        raise IdentityError("missing_issuer", "Token carries no issuer")
    issuer = _normalize_issuer(issuer)

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise IdentityError("missing_subject", "Token carries no subject")

    token_use = claims.get("token_use")
    if token_use is not None and token_use not in ALLOWED_TOKEN_USES:
        raise IdentityError("invalid_token_use", "Unsupported token type")

    audiences = _audience(claims)

    if expected_issuer is not None:
        if issuer != _normalize_issuer(expected_issuer):
            raise IdentityError("issuer_mismatch", "Issuer is not accepted")
    if expected_client_id is not None:
        if not audiences or expected_client_id not in audiences:
            raise IdentityError(
                "audience_mismatch", "Token is not issued for this client")

    groups = claims.get("cognito:groups") or ()
    if isinstance(groups, str):
        groups = (groups,)
    elif not isinstance(groups, (list, tuple)):
        groups = ()
    groups = tuple(str(g) for g in groups)

    return OwnerIdentity(
        issuer=issuer,
        subject=subject,
        client_id=audiences[0] if audiences else None,
        token_use=token_use,
        groups=groups,
    )


__all__ = [
    "ALLOWED_TOKEN_USES",
    "IdentityError",
    "OwnerIdentity",
    "owner_key",
    "extract_identity",
]
