"""MO-RC4-P02A — Identitaetsaufloesung: Kollisionen, Namensraeume, Legacy."""

import unittest

from errors import OrderError
from identity import (
    IDENTITY_ITEM_FIELDS,
    IDENTITY_VERSION,
    IDENTITY_VERSION_LEGACY,
    SOURCE_API_V1,
    SOURCE_LEGACY_SUBJECT,
    SOURCE_LEGACY_UNOWNED,
    OrderIdentity,
    classify_ownership,
    derive_consumer_id,
    resolve_order_identity,
)

ISS_A = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_POOLA"
ISS_B = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_POOLB"


def claims(sub="user-1", iss=ISS_A, client="client-1", **extra):
    data = {"sub": sub, "iss": iss, "client_id": client}
    data.update(extra)
    return data


class TestConsumerNamespaces(unittest.TestCase):
    def test_consumer_id_includes_issuer_and_client(self):
        consumer = derive_consumer_id(claims())
        self.assertEqual(
            consumer,
            "cognito:cognito-idp.eu-central-1.amazonaws.com/eu-central-1_POOLA#client-1",
        )

    def test_aud_is_accepted_as_client(self):
        self.assertEqual(
            derive_consumer_id(claims(client=None, aud="client-aud")),
            "cognito:cognito-idp.eu-central-1.amazonaws.com/eu-central-1_POOLA#client-aud",
        )
        self.assertEqual(
            derive_consumer_id(claims(client=None, aud=["single-aud"])),
            "cognito:cognito-idp.eu-central-1.amazonaws.com/eu-central-1_POOLA#single-aud",
        )

    def test_missing_issuer_or_client_is_rejected(self):
        for broken in (
            claims(iss=None),
            claims(client=None, aud=None),
            claims(iss="   "),
            claims(iss=12345),
            claims(client=""),
            claims(client=None, aud=["a", "b"]),
        ):
            with self.subTest(claims=broken):
                with self.assertRaises(OrderError) as ctx:
                    derive_consumer_id(broken)
                self.assertEqual(ctx.exception.code, "UNAUTHORIZED")


class TestOwnerActorSeparation(unittest.TestCase):
    def test_user_is_owner_and_actor(self):
        identity = resolve_order_identity(claims(sub="user-42"))
        self.assertEqual(identity.owner_type, "user")
        self.assertEqual(identity.owner_id, "user-42")
        self.assertEqual(identity.actor_type, "user")
        self.assertEqual(identity.actor_id, "user-42")
        self.assertEqual(identity.identity_version, IDENTITY_VERSION)

    def test_agent_can_act_for_user_without_becoming_owner(self):
        """Modell belegt die Trennung; Delegation selbst bleibt BLOCKED."""
        delegated = OrderIdentity(
            consumer_id="cognito:issuer#client",
            owner_type="user",
            owner_id="user-42",
            actor_type="agent",
            actor_id="agent-7",
        )
        fields = delegated.to_item_fields()
        self.assertEqual(fields["ownerId"], "user-42")
        self.assertEqual(fields["actorId"], "agent-7")
        self.assertNotEqual(fields["ownerId"], fields["actorId"])

    def test_delegated_resolution_is_blocked(self):
        with self.assertRaises(OrderError) as ctx:
            resolve_order_identity(claims(), delegated={"ownerId": "user-42", "actorId": "agent-7"})
        self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")
        self.assertIn("delegation contract", ctx.exception.message)

    def test_service_owner_type_is_expressible_but_not_resolvable(self):
        service_owned = OrderIdentity(
            consumer_id="cognito:issuer#client",
            owner_type="service",
            owner_id="svc-1",
            actor_type="service",
            actor_id="svc-1",
        )
        self.assertEqual(service_owned.owner_type, "service")
        with self.assertRaises(OrderError):
            OrderIdentity(
                consumer_id="cognito:issuer#client",
                owner_type="robot",
                owner_id="x",
                actor_type="user",
                actor_id="u",
            )


class TestCollisionPrevention(unittest.TestCase):
    def _identity(self, consumer="c1", owner_type="user", owner="u1", actor_type="user", actor="u1"):
        return OrderIdentity(consumer, owner_type, owner, actor_type, actor)

    def test_same_identity_is_stable(self):
        first = self._identity().canonical_key()
        second = resolve_order_identity(claims(sub="u1"))
        # gleiche Bestandteile -> gleicher Schluessel (auch ueber Dataclass-Grenzen)
        self.assertEqual(first, self._identity().canonical_key())
        self.assertTrue(second.canonical_key().endswith("|user|2:u1"))

    def test_same_owner_different_consumer_does_not_collide(self):
        a = self._identity(consumer="c1").canonical_key()
        b = self._identity(consumer="c2").canonical_key()
        self.assertNotEqual(a, b)

    def test_same_id_different_owner_type_does_not_collide(self):
        user = self._identity(owner_type="user", owner="x").canonical_key()
        agent = self._identity(owner_type="agent", owner="x").canonical_key()
        service = self._identity(owner_type="service", owner="x").canonical_key()
        self.assertEqual(len({user, agent, service}), 3)

    def test_delimiters_cannot_merge_identities(self):
        """Laengenpraefixe verhindern Trenner-Injection."""
        cases = [
            ("a|b", "user", "c"),
            ("a", "user", "b|c"),
            ("a|b", "user", "c|d"),
            ("a", "user", "b"),
        ]
        keys = {self._identity(consumer=c, owner_type=t, owner=o).canonical_key()
                for c, t, o in cases}
        self.assertEqual(len(keys), len(cases))

    def test_repeated_resolution_is_stable(self):
        keys = {resolve_order_identity(claims(sub="user-9")).canonical_key() for _ in range(5)}
        self.assertEqual(len(keys), 1)

    def test_invalid_components_cannot_form_keys(self):
        for bad in ("", "   ", "x" * 257, "bad\x00id"):
            with self.subTest(component=repr(bad)):
                with self.assertRaises(OrderError):
                    self._identity(owner=bad).canonical_key()


class TestIdentityValidation(unittest.TestCase):
    def test_missing_or_invalid_subject_is_rejected(self):
        for broken in ({}, {"sub": "   "}, {"sub": 42}, {"sub": "x" * 257},
                       {"sub": "bad\x01id"}):
            with self.subTest(claims=broken):
                with self.assertRaises(OrderError) as ctx:
                    resolve_order_identity(broken)
                self.assertEqual(ctx.exception.code, "UNAUTHORIZED")

    def test_item_fields_are_the_documented_set(self):
        fields = resolve_order_identity(claims()).to_item_fields()
        self.assertEqual(set(fields), set(IDENTITY_ITEM_FIELDS))
        self.assertEqual(fields["identityVersion"], IDENTITY_VERSION)


class TestLegacyClassification(unittest.TestCase):
    def test_api_v1_item(self):
        item = {
            "subjectId": "user-1",
            "consumerId": "cognito:iss#client",
            "ownerType": "user",
            "ownerId": "user-1",
            "actorType": "user",
            "actorId": "user-1",
            "identityVersion": 1,
        }
        result = classify_ownership(item)
        self.assertEqual(result["ownerSource"], SOURCE_API_V1)
        self.assertEqual(result["consumerId"], "cognito:iss#client")
        self.assertEqual(result["identityVersion"], 1)

    def test_legacy_item_with_subject_only(self):
        result = classify_ownership({"subjectId": "user-1"})
        self.assertEqual(result["ownerSource"], SOURCE_LEGACY_SUBJECT)
        self.assertEqual(result["ownerType"], "user")
        self.assertEqual(result["ownerId"], "user-1")
        self.assertIsNone(result["consumerId"])
        self.assertEqual(result["identityVersion"], IDENTITY_VERSION_LEGACY)

    def test_legacy_unowned_item_invents_nothing(self):
        result = classify_ownership({"orderId": "ord_1"})
        self.assertEqual(result["ownerSource"], SOURCE_LEGACY_UNOWNED)
        self.assertIsNone(result["ownerId"])
        self.assertIsNone(result["ownerType"])
        self.assertIsNone(result["consumerId"])


if __name__ == "__main__":
    unittest.main()
