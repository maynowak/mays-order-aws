"""MO-RC4-P02A — zentrale interne Identitaetsaufloesung fuer Bestellungen.

Modell (Entwurf, intern — kein oeffentlicher API-Vertrag):

    OrderIdentity
      consumerId        verifizierter Consumer (Cognito-Pool + App-Client)
      ownerType         user | agent | service
      ownerId           Identitaet des Eigentuemers
      actorType         user | agent | service (ausfuehrender Akteur)
      actorId           Identitaet des ausfuehrenden Akteurs
      identityVersion   1 = aufgeloest, 0 = Legacy (nur subjectId bekannt)

Grundsaetze:
- Die Identitaet stammt ausschliesslich aus einem verifizierten Kontext
  (JWT-Claims des API-Gateway-Authorizers). Client-/Body-Werte sind NIE
  vertrauenswuerdig.
- Owner und Actor sind getrennte Felder; der Actor wird nie automatisch Owner.
- Delegation (Agent/Dienst handelt fuer einen Benutzer) ist ohne nachweisbaren
  Berechtigungsvertrag BLOCKED — es gibt keinen Fallback.
- Der kanonische Schluessel ist kollisionsfrei durch Laengenpraefixe, d.h.
  Trennzeichen in Komponenten koennen keine Identitaeten vermischen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from errors import unauthorized_error, validation_error

IDENTITY_VERSION = 1
IDENTITY_VERSION_LEGACY = 0

OWNER_TYPE_USER = "user"
OWNER_TYPE_AGENT = "agent"
OWNER_TYPE_SERVICE = "service"
IDENTITY_TYPES = (OWNER_TYPE_USER, OWNER_TYPE_AGENT, OWNER_TYPE_SERVICE)

MAX_ID_LENGTH = 256

# Persistierte Attributnamen (bewusst NICHT Teil der API-Antworten).
ITEM_CONSUMER_ID = "consumerId"
ITEM_OWNER_TYPE = "ownerType"
ITEM_OWNER_ID = "ownerId"
ITEM_ACTOR_TYPE = "actorType"
ITEM_ACTOR_ID = "actorId"
ITEM_IDENTITY_VERSION = "identityVersion"

IDENTITY_ITEM_FIELDS = (
    ITEM_CONSUMER_ID,
    ITEM_OWNER_TYPE,
    ITEM_OWNER_ID,
    ITEM_ACTOR_TYPE,
    ITEM_ACTOR_ID,
    ITEM_IDENTITY_VERSION,
)

# Herkunft der Eigentuemerzuordnung (nur Klassifikation, keine Mutation).
SOURCE_API_V1 = "api_v1"
SOURCE_LEGACY_SUBJECT = "legacy_subject"
SOURCE_LEGACY_UNOWNED = "legacy_unowned"


def _clean_component(value: Any, name: str) -> Optional[str]:
    """Normalisiert ein Identitaetsfragment; None wenn unbrauchbar."""
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or len(candidate) > MAX_ID_LENGTH:
        return None
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in candidate):
        return None
    return candidate


def _auth_component(value: Any, name: str) -> str:
    cleaned = _clean_component(value, name)
    if cleaned is None:
        raise unauthorized_error(f"Invalid {name}")
    return cleaned


def _value_component(value: Any, name: str) -> str:
    cleaned = _clean_component(value, name)
    if cleaned is None:
        raise validation_error(f"Invalid {name}")
    return cleaned


def _claims_from_event(event: Mapping[str, Any]) -> Dict[str, Any]:
    """JWT-Claims aus einem HTTP-API-v2-Event (defensiv auch REST-Stil)."""
    request_context = event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}
    claims: Dict[str, Any] = {}

    jwt = authorizer.get("jwt") if isinstance(authorizer, Mapping) else None
    if isinstance(jwt, Mapping):
        raw_claims = jwt.get("claims")
        if isinstance(raw_claims, Mapping):
            claims = dict(raw_claims)

    if not claims and isinstance(authorizer, Mapping):
        claims = {
            key: value
            for key, value in authorizer.items()
            if key in ("sub", "iss", "client_id", "aud", "token_use", "username")
        }
    return claims


def _normalize_issuer(issuer: Any) -> Optional[str]:
    if not isinstance(issuer, str):
        return None
    normalized = issuer.strip()
    for scheme in ("https://", "http://"):
        if normalized.startswith(scheme):
            normalized = normalized[len(scheme):]
            break
    return normalized.rstrip("/") or None


def _client_from_claims(claims: Mapping[str, Any]) -> Optional[str]:
    client = claims.get("client_id")
    if isinstance(client, str) and client.strip():
        return client.strip()
    audience = claims.get("aud")
    if isinstance(audience, str) and audience.strip():
        return audience.strip()
    if isinstance(audience, (list, tuple)) and len(audience) == 1:
        only = audience[0]
        if isinstance(only, str) and only.strip():
            return only.strip()
    return None


def derive_consumer_id(claims: Mapping[str, Any]) -> str:
    """Consumer-Identitaet aus verifizierten Claims: `cognito:<issuer>#<client>`.

    Ohne Issuer ODER Client gibt es keinen Fallback (fail-closed), denn ohne
    Consumer ist die Identitaet nicht eindeutig abgrenzbar.
    """
    issuer = _normalize_issuer(claims.get("iss"))
    if issuer is None:
        raise unauthorized_error("Missing verified consumer identity")
    client = _client_from_claims(claims)
    if client is None:
        raise unauthorized_error("Missing verified consumer identity")
    return f"cognito:{_auth_component(issuer, 'consumer issuer')}#{_auth_component(client, 'consumer client')}"


@dataclass(frozen=True)
class OrderIdentity:
    """Kanonische Identitaet einer Bestellung (intern)."""

    consumer_id: str
    owner_type: str
    owner_id: str
    actor_type: str
    actor_id: str
    identity_version: int = IDENTITY_VERSION

    def __post_init__(self) -> None:
        if self.owner_type not in IDENTITY_TYPES:
            raise validation_error(f"Unsupported ownerType '{self.owner_type}'")
        if self.actor_type not in IDENTITY_TYPES:
            raise validation_error(f"Unsupported actorType '{self.actor_type}'")

    def canonical_key(self) -> str:
        """Kollisionsfreier Schluessel: consumerId + ownerType + ownerId.

        Laengenpraefixe verhindern, dass Trennzeichen in Komponenten
        unterschiedliche Identitaeten zu einem Schluessel verschmelzen.
        """
        consumer = _value_component(self.consumer_id, "consumerId")
        owner = _value_component(self.owner_id, "ownerId")
        return (
            f"v{self.identity_version}|{len(consumer)}:{consumer}"
            f"|{self.owner_type}|{len(owner)}:{owner}"
        )

    def to_item_fields(self) -> Dict[str, Any]:
        """Persistierte Felder (additiv; subjectId/GSI2 bleiben unveraendert)."""
        return {
            ITEM_CONSUMER_ID: self.consumer_id,
            ITEM_OWNER_TYPE: self.owner_type,
            ITEM_OWNER_ID: self.owner_id,
            ITEM_ACTOR_TYPE: self.actor_type,
            ITEM_ACTOR_ID: self.actor_id,
            ITEM_IDENTITY_VERSION: self.identity_version,
        }


def resolve_order_identity(
    claims: Mapping[str, Any],
    *,
    delegated: Optional[Mapping[str, Any]] = None,
) -> OrderIdentity:
    """Loest die Identitaet einer Bestellung auf.

    Ohne Delegationsvertrag gilt: der verifizierte Benutzer ist Owner UND
    Actor. Ein `delegated`-Kontext wird nicht interpretiert, sondern
    kontrolliert abgelehnt (BLOCKED, siehe P02A-INTEGRATION-GATES).
    """
    if delegated is not None:
        raise validation_error(
            "Delegated order creation is not supported: no verified delegation "
            "contract exists (owner/actor separation requires a signed context)"
        )

    if "sub" not in claims:
        raise unauthorized_error("Missing authenticated user identity")
    subject = _auth_component(claims.get("sub"), "authenticated user identity")
    consumer_id = derive_consumer_id(claims)

    return OrderIdentity(
        consumer_id=consumer_id,
        owner_type=OWNER_TYPE_USER,
        owner_id=subject,
        actor_type=OWNER_TYPE_USER,
        actor_id=subject,
        identity_version=IDENTITY_VERSION,
    )


def resolve_order_identity_from_event(event: Mapping[str, Any]) -> OrderIdentity:
    """Einstieg fuer den Order-Handler (HTTP-API-v2-Event)."""
    return resolve_order_identity(_claims_from_event(event))


def extract_verified_subject(event: Mapping[str, Any]) -> str:
    """Nur die verifizierte Benutzer-ID (Kompatibilitaets-Helper zu P02)."""
    return resolve_order_identity_from_event(event).owner_id


def classify_ownership(item: Mapping[str, Any]) -> Dict[str, Any]:
    """Klassifiziert die Eigentuemerzuordnung eines gespeicherten Items.

    Es wird NIE eine Zuordnung erfunden:
    - api_v1: vollstaendige Identitaet (identityVersion >= 1)
    - legacy_subject: nur subjectId (P02-Vertrag: sub = Benutzer)
    - legacy_unowned: keine subjectId (RIS-Direktschreibung, Altbestand)
    """
    subject = item.get("subjectId")
    version = item.get(ITEM_IDENTITY_VERSION)
    if isinstance(subject, str) and subject and isinstance(version, int) and version >= IDENTITY_VERSION:
        return {
            "ownerSource": SOURCE_API_V1,
            "ownerType": item.get(ITEM_OWNER_TYPE, OWNER_TYPE_USER),
            "ownerId": item.get(ITEM_OWNER_ID, subject),
            "consumerId": item.get(ITEM_CONSUMER_ID),
            "identityVersion": version,
        }
    if isinstance(subject, str) and subject:
        return {
            "ownerSource": SOURCE_LEGACY_SUBJECT,
            "ownerType": OWNER_TYPE_USER,
            "ownerId": subject,
            "consumerId": None,
            "identityVersion": IDENTITY_VERSION_LEGACY,
        }
    return {
        "ownerSource": SOURCE_LEGACY_UNOWNED,
        "ownerType": None,
        "ownerId": None,
        "consumerId": None,
        "identityVersion": None,
    }
