"""Learning-first delivery digests cover every row actually trained."""
from types import SimpleNamespace as NS
from unittest.mock import patch

from bilqis_mlx.factory.teaching import content_digest
from bilqis_mlx.runtime.factory_training_bridge import _compile_factory_training


def test_learning_first_delivery_digest_covers_rehearsal_rows():
    direct = ({"id": "direct", "capability": "A.PARENT"},)
    rehearsal = ({"id": "prior", "capability": "A.IDENTITY"},)
    rows = (*direct, *rehearsal)
    delivery = NS(specimen_content_sha256=content_digest(direct))

    with patch(
            "bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode."
            "strict_evidence_enabled",
            return_value=False), patch(
            "bilqis_mlx.runtime.factory_training_bridge."
            "compile_learning_first_training_batch",
            return_value="compiled") as compiler:
        result = _compile_factory_training(
            rows, object(), NS(topology=object()), delivery, "A.PARENT", {},
            len(rows), 1, object(), None, {"prior": "prior"}, {}, (), "feature",
            "generation", object(), None, ())

    assert result == "compiled"
    assert delivery.specimen_content_sha256 == content_digest(direct)
    assert compiler.call_args.kwargs["delivered_content_sha256"] == content_digest(rows)
