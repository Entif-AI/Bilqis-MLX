"""CT-055 Akasha security, namespace and mutation boundary proof."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.akasha_domains import AkashaDomain, DOMAIN_CONTRACTS
from bilqis_mlx.runtime.akasha_security import (
    AkashaAuthorityTarget,
    AkashaNamespaceScope,
    AkashaWriteRequest,
    DOMAIN_SECURITY_POLICIES,
    authorize_akasha_write,
)


CURRENT = "a" * 64
AUTHORITY_RECEIPT = "b" * 64
SCOPE = AkashaNamespaceScope("entif", "bilqis")


def _request(domain=AkashaDomain.RECEIPT_PROVENANCE, *, current=CURRENT, **overrides):
    policy = DOMAIN_SECURITY_POLICIES[domain]
    values = {
        "domain": domain,
        "writer_id": "writer-1",
        "writer_role": policy.writer_role,
        "tenant_id": SCOPE.tenant_id,
        "project_id": SCOPE.project_id,
        "namespace": SCOPE.namespace_for(domain),
        "operation": policy.allowed_operations[0],
        "target": AkashaAuthorityTarget.DERIVED_PROJECTION,
        "expected_version_sha256": current,
        "authority_receipt_sha256": AUTHORITY_RECEIPT,
    }
    values.update(overrides)
    return AkashaWriteRequest(**values)


class AkashaSecurityPolicyTests(unittest.TestCase):
    def test_every_domain_policy_preserves_authority_and_declared_operations(self):
        self.assertEqual(set(DOMAIN_SECURITY_POLICIES), set(AkashaDomain))
        for domain, policy in DOMAIN_SECURITY_POLICIES.items():
            with self.subTest(domain=domain.value):
                contract = DOMAIN_CONTRACTS[domain]
                self.assertEqual(policy.authority_owner, contract.authority_owner)
                self.assertEqual(policy.allowed_operations, contract.allowed_operations)
                self.assertEqual(
                    policy.writer_identity_class, "authenticated-principal-id")
                self.assertTrue(policy.writer_role)
                self.assertTrue(policy.read_scopes)
                self.assertTrue(policy.audit_obligations)
                self.assertEqual(policy.namespace_rule, "tenant/project/domain")
                self.assertEqual(
                    policy.allowed_target,
                    AkashaAuthorityTarget.DERIVED_PROJECTION)
                self.assertEqual(
                    set(policy.forbidden_targets), {
                        AkashaAuthorityTarget.CANONICAL_SEMANTIC_SOURCE,
                        AkashaAuthorityTarget.HISTORICAL_EVIDENCE_SOURCE,
                    })

    def test_valid_request_returns_deterministic_policy_bound_authorization(self):
        request = _request()
        first = authorize_akasha_write(
            SCOPE, request, current_version_sha256=CURRENT)
        second = authorize_akasha_write(
            SCOPE, request, current_version_sha256=CURRENT)
        self.assertEqual(first, second)
        self.assertEqual(first.request_sha256, request.request_sha256)
        self.assertEqual(
            first.policy_sha256,
            DOMAIN_SECURITY_POLICIES[request.domain].policy_sha256)
        self.assertIn(first.authorization_sha256, first.canonical_json)

    def test_writer_identity_is_bound_without_freezing_a_transport_identity(self):
        first = _request(writer_id="writer-1")
        second = _request(writer_id="writer-2")
        self.assertNotEqual(first.request_sha256, second.request_sha256)
        self.assertNotEqual(
            authorize_akasha_write(
                SCOPE, first, current_version_sha256=CURRENT).authorization_sha256,
            authorize_akasha_write(
                SCOPE, second, current_version_sha256=CURRENT).authorization_sha256)

    def test_empty_projection_requires_an_explicit_empty_precondition(self):
        request = _request(current=None)
        authorization = authorize_akasha_write(
            SCOPE, request, current_version_sha256=None)
        self.assertIsNone(authorization.current_version_sha256)

    def test_semantic_projection_cannot_redefine_canonical_source_meaning(self):
        request = _request(
            AkashaDomain.SEMANTIC_GRAPH,
            target=AkashaAuthorityTarget.CANONICAL_SEMANTIC_SOURCE)
        with self.assertRaises(BilqisError) as caught:
            authorize_akasha_write(SCOPE, request, current_version_sha256=CURRENT)
        self.assertEqual(
            caught.exception.context["reason"],
            "AKASHA_WRITE_CANONICAL_MUTATION_FORBIDDEN")

    def test_historical_evidence_domains_cannot_overwrite_source_history(self):
        for domain in (
            AkashaDomain.LEARNER_EVIDENCE,
            AkashaDomain.RUN_HISTORY,
            AkashaDomain.RECEIPT_PROVENANCE,
        ):
            with self.subTest(domain=domain.value):
                request = _request(
                    domain,
                    target=AkashaAuthorityTarget.HISTORICAL_EVIDENCE_SOURCE)
                with self.assertRaises(BilqisError) as caught:
                    authorize_akasha_write(
                        SCOPE, request, current_version_sha256=CURRENT)
                self.assertEqual(
                    caught.exception.context["reason"],
                    "AKASHA_WRITE_CANONICAL_MUTATION_FORBIDDEN")

    def test_wrong_tenant_project_or_namespace_fails_closed(self):
        request = _request()
        for changed in (
            replace(request, tenant_id="other"),
            replace(request, project_id="other"),
            replace(request, namespace="entif/other/receipt-provenance"),
        ):
            with self.subTest(request=changed):
                with self.assertRaises(BilqisError) as caught:
                    authorize_akasha_write(
                        SCOPE, changed, current_version_sha256=CURRENT)
                self.assertEqual(
                    caught.exception.context["reason"],
                    "AKASHA_WRITE_NAMESPACE_FORBIDDEN")

    def test_stale_expected_version_fails_instead_of_rebasing(self):
        request = _request(current="c" * 64)
        with self.assertRaises(BilqisError) as caught:
            authorize_akasha_write(SCOPE, request, current_version_sha256=CURRENT)
        self.assertEqual(
            caught.exception.context["reason"],
            "AKASHA_WRITE_EXPECTED_VERSION_STALE")

    def test_wrong_writer_role_or_domain_operation_fails_closed(self):
        request = _request()
        cases = (
            (replace(request, writer_role="mission-control"),
             "AKASHA_WRITE_ROLE_FORBIDDEN"),
            (replace(request, operation="overwrite"),
             "AKASHA_WRITE_OPERATION_FORBIDDEN"),
        )
        for changed, reason in cases:
            with self.subTest(reason=reason):
                with self.assertRaises(BilqisError) as caught:
                    authorize_akasha_write(
                        SCOPE, changed, current_version_sha256=CURRENT)
                self.assertEqual(caught.exception.context["reason"], reason)

    def test_policy_is_transport_neutral_and_contains_no_broker_identity(self):
        request = _request()
        record = DOMAIN_SECURITY_POLICIES[request.domain].to_record()
        self.assertNotIn("broker", record)
        self.assertNotIn("transport", record)
        self.assertNotIn("mission_control", record)
        self.assertEqual(
            authorize_akasha_write(
                SCOPE, request, current_version_sha256=CURRENT).domain,
            request.domain)


if __name__ == "__main__":
    unittest.main()
