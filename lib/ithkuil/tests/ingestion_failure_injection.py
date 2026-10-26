"""Inject one extra census row into the real conformance command."""
import subprocess
from pathlib import Path

def fail_no_omission(argv, cwd, env, timeout):
    if "lib.ithkuil.src.skos.conformance" not in argv:
        completed = subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                                    text=False, timeout=timeout, check=False)
        return {"exit_code": completed.returncode,
                "stdout": completed.stdout, "stderr": completed.stderr}
    from lib.ithkuil.src.skos.canonical import canonicalize
    from lib.ithkuil.src.skos.corpus import compile_domains, source_census
    from lib.ithkuil.src.skos.publication import json_bytes

    input_root = Path(argv[argv.index("--input-root") + 1])
    output_root = Path(argv[argv.index("--output-root") + 1])
    build, admitted = compile_domains(input_root)
    comparison, _ = compile_domains(input_root)
    rows = [{"domain": row.domain, "table": row.table, "key": row.key}
            for row in source_census(input_root)]
    rows.append({"domain": "atomic", "table": "morphemes_atomic",
                 "key": "INJECTED-NO-OMISSION-FAILURE"})
    injected = output_root.parent / "injected-conformance-inputs"
    injected.mkdir()
    (injected / "canonical.nt").write_bytes(canonicalize(build.graph).payload)
    (injected / "comparison.nt").write_bytes(canonicalize(comparison.graph).payload)
    (injected / "coverage.json").write_bytes(json_bytes(build.receipt))
    (injected / "source-rows.json").write_bytes(json_bytes(rows))
    from rdflib import Graph
    support = Graph()
    for triple in admitted:
        support.add(triple)
    (injected / "admitted-mappings.nt").write_bytes(canonicalize(support).payload)
    command = [argv[0], "-B", "-m", "lib.ithkuil.src.skos.conformance",
               "--rdf", str(injected / "canonical.nt"),
               "--coverage", str(injected / "coverage.json"),
               "--source-rows", str(injected / "source-rows.json"),
               "--comparison-rdf", str(injected / "comparison.nt"),
               "--admitted-mappings", str(injected / "admitted-mappings.nt"),
               "--output-root", str(output_root)]
    completed = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                               text=False, timeout=timeout, check=False)
    return {"exit_code": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr}
