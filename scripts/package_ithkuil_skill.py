"""Stage the governed Skill with its canonical bounded fixture, then package upstream.

Validators and the upstream Skill Creator are explicit tool inputs, never bundled.
The generated package contains workflow instructions and fixture inputs only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

SKILL_FILES = (
    "SKILL.md", "PROJECT_GOVERNANCE.yaml", "agents/openai.yaml",
    "references/authority.md", "references/source.md", "references/semantic.md",
    "references/graph.md", "references/fixture.md", "references/package.md",
    "scripts/cleanroom.py",
)


def stage(repo: Path, output: Path) -> Path:
    source = repo / "skills/ithkuil-ingestion"
    fixture = repo / "lib/ithkuil/tests/fixtures/ingestion"
    actual = {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}
    if actual != set(SKILL_FILES):
        raise ValueError("SKILL_RESOURCE_CLOSURE_MISMATCH")
    for base in (source, fixture):
        if any(p.is_symlink() for p in base.rglob("*")):
            raise ValueError("SKILL_SYMLINK_FORBIDDEN")
    descriptor = json.loads((fixture / "descriptor.json").read_text())
    expected_fixture = {"descriptor.json", "smoke.json", descriptor["excerpt"]["path"],
                        descriptor["configuration_excerpt"]["path"],
                        *("csv/" + name for name in descriptor["seed_csv"])}
    actual_fixture = {p.relative_to(fixture).as_posix() for p in fixture.rglob("*") if p.is_file()}
    if actual_fixture != expected_fixture:
        raise ValueError("SKILL_FIXTURE_CLOSURE_MISMATCH")
    target = output / "ithkuil-ingestion"
    shutil.copytree(source, target)
    shutil.copytree(fixture, target / "assets/fixture")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--governance-validator", type=Path, required=True)
    parser.add_argument("--upstream-validator", type=Path, required=True)
    parser.add_argument("--skill-creator", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=False)
    skill = stage(args.repo.resolve(), output / "staged")
    for validator in (args.governance_validator, args.upstream_validator):
        subprocess.run([sys.executable, "-B", str(validator.resolve()), str(skill)], check=True)
    subprocess.run([sys.executable, "-B", "-m", "scripts.package_skill", str(skill), str(output)],
                   cwd=args.skill_creator.resolve(), check=True)


if __name__ == "__main__":
    main()
