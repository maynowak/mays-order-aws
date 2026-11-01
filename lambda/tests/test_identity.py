"""MO-RC4-P02A — Identitaetsaufloesung: Kollisionen, Namensraeume, Legacy."""

import unittest

from errors import OrderError
from identity import (
    IDENTITY_ITEM_FIELDS,
    IDENTITY_VERSION,
    IDENTITY_VERSION_LEGACY,
    SOURCE_API_V1,
    SOURCE_INCONSISTENT,
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
            "identityVerification": "verified_jwt",
        }
        result = classify_ownership(item)
        self.assertEqual(result["ownerSource"], SOURCE_API_V1)
        self.assertEqual(result["consumerId"], "cognito:iss#client")
        self.assertEqual(result["identityVersion"], 1)
        self.assertEqual(result["verificationContext"], "verified_jwt")

    def test_binding_without_verification_context_is_inconsistent(self):
        """Eine Bindung ohne Verifikationsnachweis gilt NICHT als verifiziert."""
        item = {
            "subjectId": "user-1",
            "consumerId": "cognito:iss#client",
            "ownerId": "user-1",
            "identityVersion": 1,
        }
        result = classify_ownership(item)
        self.assertEqual(result["ownerSource"], SOURCE_INCONSISTENT)
        self.assertIsNone(result["verificationContext"])

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


class TestInternalIdentityResolutionP02B(unittest.TestCase):
    """Interne Consumer (RIS) erhalten nur mit verifiziertem Kontext eine Bindung."""

    CONTEXT = {
        "verificationContext": "verified_jwt",
        "consumerId": "cognito:iss#client",
        "ownerType": "user",
        "ownerId": "user-1",
        "actorType": "user",
        "actorId": "user-1",
    }

    def test_verified_user_context_yields_binding(self):
        from identity import InternalOrderIdentity, resolve_internal_order_identity
        identity = resolve_internal_order_identity(dict(self.CONTEXT))
        self.assertIsInstance(identity, InternalOrderIdentity)
        self.assertEqual(identity.owner_id, "user-1")
        self.assertEqual(identity.actor_id, "user-1")
        self.assertEqual(identity.verification_context, "verified_jwt")
        self.assertEqual(identity.to_item_fields()["identityVerification"], "verified_jwt")

    def test_unverified_or_missing_context_is_blocked(self):
        from identity import resolve_internal_order_identity
        for broken in (
            {},
            {"verificationContext": "none"},
            {"verificationContext": "verified_internal_signed"},  # nicht implementiert
            {"verificationContext": "trust_me"},
            None,
            "verified_jwt",
        ):
            with self.subTest(context=broken):
                with self.assertRaises(OrderError) as ctx:
                    resolve_internal_order_identity(broken)
                self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")

    def test_order_data_is_never_an_identity_source(self):
        from identity import resolve_internal_order_identity
        forged_order = {"subjectId": "victim", "ownerId": "victim", "consumerId": "x#y"}
        with self.assertRaises(OrderError):
            resolve_internal_order_identity({}, forged_order)

    def test_owner_actor_separation_requires_signed_context(self):
        from identity import resolve_internal_order_identity
        separated = dict(self.CONTEXT, actorType="agent", actorId="agent-7")
        with self.assertRaises(OrderError) as ctx:
            resolve_internal_order_identity(separated)
        self.assertIn("signed verification context", ctx.exception.message)

    def test_non_user_owner_types_are_not_enabled(self):
        from identity import resolve_internal_order_identity
        for owner_type in ("agent", "service"):
            with self.subTest(owner_type=owner_type):
                with self.assertRaises(OrderError):
                    resolve_internal_order_identity(
                        dict(self.CONTEXT, ownerType=owner_type, actorType=owner_type)
                    )

    def test_manipulated_components_are_rejected(self):
        from identity import resolve_internal_order_identity
        for field, bad in (
            ("consumerId", ""),
            ("consumerId", "x\x00y"),
            ("ownerId", "  "),
            ("ownerId", "u" * 257),
            ("ownerId", 123),
        ):
            with self.subTest(field=field, value=repr(bad)):
                with self.assertRaises(OrderError):
                    resolve_internal_order_identity(dict(self.CONTEXT, **{field: bad}))

    def test_repeated_resolution_is_stable(self):
        from identity import resolve_internal_order_identity
        keys = {
            resolve_internal_order_identity(dict(self.CONTEXT)).canonical_key()
            for _ in range(5)
        }
        self.assertEqual(len(keys), 1)

    def test_identity_rejects_unverified_verification_context(self):
        with self.assertRaises(OrderError):
            OrderIdentity(
                consumer_id="c#x", owner_type="user", owner_id="u",
                actor_type="user", actor_id="u", verification_context="none",
            )


class TestPrivacyScopeP02B(unittest.TestCase):
    """Consumer-Isolation: gleiche Owner-ID, unterschiedliche Consumer."""

    def test_scope_is_optional(self):
        from identity import item_in_privacy_scope, privacy_scope_consumer
        self.assertIsNone(privacy_scope_consumer({}))
        self.assertIsNone(privacy_scope_consumer(None))
        self.assertEqual(
            privacy_scope_consumer({"consumerId": "cognito:iss#client"}),
            "cognito:iss#client",
        )
        self.assertEqual(
            privacy_scope_consumer({"consumer": "cognito:iss#client"}),
            "cognito:iss#client",
        )

    def test_no_scope_keeps_everything_visible(self):
        from identity import item_in_privacy_scope
        self.assertTrue(item_in_privacy_scope({"subjectId": "u"}, None))
        self.assertTrue(item_in_privacy_scope({}, None))

    def test_scope_excludes_other_consumers_and_legacy(self):
        from identity import item_in_privacy_scope
        mine = {"subjectId": "u1", "consumerId": "consumer-a"}
        other = {"subjectId": "u1", "consumerId": "consumer-b"}
        legacy = {"subjectId": "u1"}

        self.assertTrue(item_in_privacy_scope(mine, "consumer-a"))
        self.assertFalse(item_in_privacy_scope(other, "consumer-a"))
        self.assertFalse(item_in_privacy_scope(legacy, "consumer-a"))

    def test_legacy_items_have_no_consumer(self):
        from identity import classify_ownership
        self.assertIsNone(classify_ownership({"subjectId": "u1"})["consumerId"])
