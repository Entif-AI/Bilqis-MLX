"""Measure the existing failing DAG import boundary without weakening its test."""
import ast
import hashlib
import importlib.util
import json
from verify_contract import ROOT, BASE, OWNER, old


def local_path(name):
    stem = ROOT.joinpath(*name.split("."))
    if stem.with_suffix(".py").is_file():
        return stem.with_suffix(".py"), False
    if (stem / "__init__.py").is_file():
        return stem / "__init__.py", True
    return None, False


def census(before):
    pending = ["bilqis_mlx.semantics.cognitive_dag"]
    seen = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        path, is_package = local_path(name)
        if path is None:
            continue
        seen.add(name)
        package = name if is_package else name.rpartition(".")[0]
        tree = old(OWNER) if before and name == "bilqis_mlx.semantics.cognitive_dag" else ast.parse(path.read_text())
        for node in ast.walk(tree):
            imports = ()
            if isinstance(node, ast.Import):
                imports = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = importlib.util.resolve_name("." * node.level + (node.module or ""), package)
                imports = (base, *(base + "." + alias.name for alias in node.names))
            pending.extend(n for n in imports if n.startswith("bilqis_mlx.") and local_path(n)[0] is not None)
    forbidden = ("bilqis_mlx.verification", "bilqis_mlx.source_adapters",
                 "bilqis_mlx.generated_assessment", "bilqis_mlx.assessment",
                 "bilqis_mlx.factory", "bilqis_mlx.runtime")
    return tuple(sorted(n for n in seen if n.startswith(forbidden) or n.endswith("_oracle")))


def main():
    before, after = census(True), census(False)
    assert before == after, {"added": sorted(set(after) - set(before)),
                             "removed": sorted(set(before) - set(after))}
    print(json.dumps({"base": BASE, "existing_forbidden_imports": len(after),
        "set_sha256": hashlib.sha256(json.dumps(after, separators=(",", ":")).encode()).hexdigest(),
        "boundary_result": "FAILED" if after else "PASS",
        "measurement": "before/after parity; not a boundary waiver"}, sort_keys=True))


if __name__ == "__main__":
    main()
