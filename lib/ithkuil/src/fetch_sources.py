#!/usr/bin/env python3
"""Snapshot the official New Ithkuil grammar surface for local parsing.

Raw pages are intentionally ignored by Git.  The tracked manifest preserves
the reproducible URL set and content identity without vendoring the source.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "_raw"
MANIFEST = ROOT / "_data" / "csv" / "sources" / "source_manifest.csv"

BASE = "https://www.ithkuil.net/"
SOURCES = [
    ("NI-WEB-INDEX", "grammar_index", "New Ithkuil grammar index", "", "index.html"),
    ("NI-WEB-CH01", "grammar_chapter", "Chapter 1: Phonology", "newithkuil_01_phonology.htm", "newithkuil_01_phonology.htm"),
    ("NI-WEB-CH02", "grammar_chapter", "Chapter 2: Morpho-Phonology", "newithkuil_02_morpho-phonology.htm", "newithkuil_02_morpho-phonology.htm"),
    ("NI-WEB-CH03", "grammar_chapter", "Chapter 3: Morphology", "newithkuil_03_morphology.htm", "newithkuil_03_morphology.htm"),
    ("NI-WEB-CH04", "grammar_chapter", "Chapter 4: Case", "newithkuil_04_case.htm", "newithkuil_04_case.htm"),
    ("NI-WEB-CH05", "grammar_chapter", "Chapter 5: Verbs", "newithkuil_05_verbs.htm", "newithkuil_05_verbs.htm"),
    ("NI-WEB-CH06", "grammar_chapter", "Chapter 6: More Verbs", "newithkuil_06_more_verbs.htm", "newithkuil_06_more_verbs.htm"),
    ("NI-WEB-CH07", "grammar_chapter", "Chapter 7: Affixes", "newithkuil_07_affixes.htm", "newithkuil_07_affixes.htm"),
    ("NI-WEB-CH08", "grammar_chapter", "Chapter 8: Adjuncts", "newithkuil_08_adjuncts.htm", "newithkuil_08_adjuncts.htm"),
    ("NI-WEB-CH09", "grammar_chapter", "Chapter 9: Referentials", "newithkuil_09_referentials.htm", "newithkuil_09_referentials.htm"),
    ("NI-WEB-CH10", "grammar_chapter", "Chapter 10: Special Constructions", "newithkuil_10_spec_constructions.htm", "newithkuil_10_spec_constructions.htm"),
    ("NI-WEB-CH11", "grammar_chapter", "Chapter 11: Syntax", "newithkuil_11_syntax.htm", "newithkuil_11_syntax.htm"),
    ("NI-WEB-CH12", "grammar_chapter", "Chapter 12: Script", "newithkuil_12_script.htm", "newithkuil_12_script.htm"),
    ("NI-WEB-CH13", "grammar_chapter", "Chapter 13: Numbers", "newithkuil_13_numbers.htm", "newithkuil_13_numbers.htm"),
    ("NI-WEB-APP", "grammar_appendix", "New Ithkuil appendices", "newithkuil_appendices.htm", "newithkuil_appendices.htm"),
    ("NI-LEXICON-SITE", "lexicon", "New Ithkuil lexicon (grammar-site link)", "newithkuil_lexicon.pdf", "newithkuil_lexicon.pdf"),
    ("NI-AFFIX-PDF", "affix_reference", "New Ithkuil affix reference", "newithkuil_affixes.pdf", "newithkuil_affixes.pdf"),
    (
        "NI-LEXICON-CURRICULUM",
        "lexicon",
        "New Ithkuil lexicon (Curriculum Registry URL variant)",
        "https://ithkuil.net/New_Ithkuil_Lexicon.pdf",
        "New_Ithkuil_Lexicon.pdf",
    ),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def last_header(headers: str, name: str) -> str:
    prefix = name.lower() + ":"
    values = [line.split(":", 1)[1].strip() for line in headers.splitlines() if line.lower().startswith(prefix)]
    return values[-1] if values else ""


def fetch(url: str, destination: Path) -> tuple[str, str, str, str]:
    """Fetch with the host's trusted curl and return response metadata."""
    with tempfile.NamedTemporaryFile(prefix="ithkuil-headers-", delete=False) as handle:
        headers_path = Path(handle.name)
    try:
        completed = subprocess.run(
            [
                "curl",
                "-L",
                "--fail",
                "--silent",
                "--show-error",
                "--user-agent",
                "Bilqis grammar research snapshot/1.0",
                "--dump-header",
                str(headers_path),
                "--output",
                str(destination),
                "--write-out",
                "%{url_effective}\n%{content_type}\n",
                url,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        metadata = completed.stdout.splitlines()
        final_url = metadata[0] if metadata else url
        content_type = metadata[1] if len(metadata) > 1 else ""
        headers = headers_path.read_text(encoding="iso-8859-1")
        return final_url, content_type, last_header(headers, "Last-Modified"), last_header(headers, "ETag")
    finally:
        headers_path.unlink(missing_ok=True)


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows: list[dict[str, str | int]] = []

    for source_id, source_type, title, relative_url, local_name in SOURCES:
        url = relative_url if relative_url.startswith(("http://", "https://")) else BASE + relative_url
        path = RAW / local_name
        final_url, content_type, last_modified, etag = fetch(url, path)
        data = path.read_bytes()
        rows.append(
            {
                "source_id": source_id,
                "source_type": source_type,
                "title": title,
                "requested_url": url,
                "final_url": final_url,
                "local_name": local_name,
                "sha256": sha256(data),
                "bytes": len(data),
                "fetched_at_utc": fetched_at,
                "content_type": content_type,
                "last_modified": last_modified,
                "etag": etag,
            }
        )

    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"snapshot sources={len(rows)} manifest={MANIFEST}")


if __name__ == "__main__":
    main()

