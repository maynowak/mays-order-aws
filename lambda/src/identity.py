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
ITEM_IDENTITY_VERIFICATION = "identityVerification"

IDENTITY_ITEM_FIELDS = (
    ITEM_CONSUMER_ID,
    ITEM_OWNER_TYPE,
    ITEM_OWNER_ID,
    ITEM_ACTOR_TYPE,
    ITEM_ACTOR_ID,
    ITEM_IDENTITY_VERSION,
    ITEM_IDENTITY_VERIFICATION,
)

# Verifikationskontext (MO-RC4-P02B): WARUM darf der Actor fuer den Owner handeln?
# Nur ausdruecklich verifizierte Kontexte duerfen eine Bindung erzeugen.
VERIFICATION_JWT = "verified_jwt"                 # API Gateway JWT (implementiert)
VERIFICATION_INTERNAL = "verified_internal_signed"  # interner Vertrag (NICHT implementiert)
VERIFICATION_NONE = "none"                        # unverifiziert (keine Bindung)
VERIFIED_CONTEXTS = (VERIFICATION_JWT,)

# Herkunft der Eigentuemerzuordnung (nur Klassifikation, keine Mutation).
SOURCE_API_V1 = "api_v1"
SOURCE_LEGACY_SUBJECT = "legacy_subject"
SOURCE_LEGACY_UNOWNED = "legacy_unowned"
SOURCE_INCONSISTENT = "inconsistent_binding"


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
    verification_context: str = VERIFICATION_JWT

    def __post_init__(self) -> None:
        if self.owner_type not in IDENTITY_TYPES:
            raise validation_error(f"Unsupported ownerType '{self.owner_type}'")
        if self.actor_type not in IDENTITY_TYPES:
            raise validation_error(f"Unsupported actorType '{self.actor_type}'")
        if self.verification_context not in VERIFIED_CONTEXTS:
            # Eine unverifizierte Identitaet darf niemals als Bindung gelten.
            raise validation_error(
                f"Unsupported verification context '{self.verification_context}'"
            )

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
            ITEM_IDENTITY_VERIFICATION: self.verification_context,
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


@dataclass(frozen=True)
class InternalOrderIdentity(OrderIdentity):
    """Identitaet aus einem internen Kontext (nicht HTTP).

    Traegt zusaetzlich den Verifikationskontext, WARUM der Actor fuer den
    Owner handeln darf. Nur verifizierte Kontexte sind zulaessig
    (siehe VERIFIED_CONTEXTS); `order`-Daten sind NIE eine Identitaetsquelle.
    """


def resolve_internal_order_identity(
    context: Mapping[str, Any],
    order: Optional[Mapping[str, Any]] = None,
) -> InternalOrderIdentity:
    """Loest eine Identitaet fuer interne Consumer (z. B. RIS) auf.

    `order` wird bewusst NICHT ausgewertet: Bestelldaten (inkl. vom Client
    uebermittelter IDs) sind keine vertrauenswuerdige Identitaetsquelle.
    Ohne verifizierten Kontext gibt es KEINE Bindung (fail-closed).
    """
    if not isinstance(context, Mapping):
        raise validation_error("Missing internal identity context")

    verification = context.get("verificationContext")
    if verification not in VERIFIED_CONTEXTS:
        raise validation_error(
            "No verified internal identity context: owner binding for internal "
            "consumers is BLOCKED until a verified trust contract exists"
        )

    consumer_id = _value_component(context.get("consumerId"), "consumerId")
    owner_type = context.get("ownerType")
    if owner_type not in IDENTITY_TYPES:
        raise validation_error(f"Unsupported ownerType '{owner_type}'")
    if owner_type != OWNER_TYPE_USER:
        raise validation_error(
            f"Owner type '{owner_type}' is not enabled: no verified owner contract"
        )
    owner_id = _value_component(context.get("ownerId"), "ownerId")

    actor_type = context.get("actorType") or owner_type
    actor_id = context.get("actorId") or owner_id
    if actor_type not in IDENTITY_TYPES:
        raise validation_error(f"Unsupported actorType '{actor_type}'")
    actor_id = _value_component(actor_id, "actorId")

    if (owner_type, owner_id) != (actor_type, actor_id):
        raise validation_error(
            "Owner/actor separation requires a signed verification context "
            "(not implemented): refusing to bind an unverified delegation"
        )

    return InternalOrderIdentity(
        consumer_id=consumer_id,
        owner_type=owner_type,
        owner_id=owner_id,
        actor_type=actor_type,
        actor_id=actor_id,
        identity_version=IDENTITY_VERSION,
        verification_context=verification,
    )


def resolve_order_identity_from_event(event: Mapping[str, Any]) -> OrderIdentity:
    """Einstieg fuer den Order-Handler (HTTP-API-v2-Event)."""
    return resolve_order_identity(_claims_from_event(event))


def authorize_order_access(item: Mapping[str, Any], identity: Optional[OrderIdentity]) -> bool:
    """Prueft Owner- UND Consumer-Berechtigung einer gespeicherten Order.

    Fail-closed: `subjectId` und `consumerId` muessen vorhanden sein und
    beide exakt zur verifizierten Identitaet passen. Legacy-Orders ohne
    vollstaendige Identitaet sind damit automatisch nicht zugaenglich.
    """
    if identity is None or not isinstance(item, Mapping):
        return False
    subject = item.get("subjectId")
    consumer = item.get("consumerId")
    if not isinstance(subject, str) or not subject:
        return False
    if not isinstance(consumer, str) or not consumer:
        return False
    return subject == identity.owner_id and consumer == identity.consumer_id


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
    verification = item.get(ITEM_IDENTITY_VERIFICATION)
    if (
        isinstance(subject, str)
        and subject
        and isinstance(version, int)
        and version >= IDENTITY_VERSION
    ):
        # Eine Bindung gilt nur mit ausdruecklich verifiziertem Kontext und
        # konsistenten Feldern; sonst wird sie NICHT als verifiziert gemeldet.
        consistent = (
            item.get(ITEM_OWNER_ID) in (None, subject)
            and verification in VERIFIED_CONTEXTS
        )
        return {
            "ownerSource": SOURCE_API_V1 if consistent else SOURCE_INCONSISTENT,
            "ownerType": item.get(ITEM_OWNER_TYPE, OWNER_TYPE_USER),
            "ownerId": item.get(ITEM_OWNER_ID, subject),
            "consumerId": item.get(ITEM_CONSUMER_ID),
            "identityVersion": version,
            "verificationContext": verification,
        }
    if isinstance(subject, str) and subject:
        return {
            "ownerSource": SOURCE_LEGACY_SUBJECT,
            "ownerType": OWNER_TYPE_USER,
            "ownerId": subject,
            "consumerId": None,
            "identityVersion": IDENTITY_VERSION_LEGACY,
            "verificationContext": None,
        }
    return {
        "ownerSource": SOURCE_LEGACY_UNOWNED,
        "ownerType": None,
        "ownerId": None,
        "consumerId": None,
        "identityVersion": None,
        "verificationContext": None,
    }


# ---------------------------------------------------------------------------
# Privacy-Scope (MO-RC4-P02B): Consumer-Isolation
# ---------------------------------------------------------------------------

def privacy_scope_consumer(context: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Liest den optionalen Consumer-Scope aus einem internen Auth-Kontext.

    Nicht gesetzt => unveraendertes Verhalten (Deployment-weiter Scope).
    Gesetzt      => Abfragen duerfen nur Items dieses Consumers sehen.
    """
    if not isinstance(context, Mapping):
        return None
    raw = context.get("consumerId") or context.get("consumer")
    if raw is None:
        return None
    return _value_component(raw, "consumerId")


def item_in_privacy_scope(item: Mapping[str, Any], consumer_id: Optional[str]) -> bool:
    """True, wenn das Item im angegebenen Consumer-Scope liegt.

    Ohne Scope immer True (rueckwaertskompatibel). Mit Scope gilt strikt:
    nur Items mit identischer `consumerId`. Legacy-Items (ohne `consumerId`)
    werden NICHT stillschweigend einem Consumer zugeschlagen.
    """
    if consumer_id is None:
        return True
    return item.get(ITEM_CONSUMER_ID) == consumer_id
