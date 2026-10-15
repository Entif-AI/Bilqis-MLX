"""Source-attested, bounded New Ithkuil morphology construction and parsing."""
from __future__ import annotations

from dataclasses import dataclass
import unicodedata
import json

NUMBER_SOURCE = "https://ithkuil.net/newithkuil_13_numbers.htm"
CASE_SOURCE = "https://ithkuil.net/newithkuil_04_case.htm"
MORPHOLOGY_SOURCE = "https://ithkuil.net/newithkuil_03_morphology.htm"

REF_GRAMMAR = CASE_SOURCE.replace("04_case", "09_referentials")

class ConstructionError(ValueError):
    """Form is outside the supported New Ithkuil grammar slice."""

REVIEW_VERSION = "mapping-review/20261015-d"
# Ch.13.2: -VR-, -LL-, -KS-, -Z-, -PŠ-, -ST-, -CP-, -NS-, -ČK-, -LẒ-.
UNITS = ("vr", "ll", "ks", "z", "pš", "st", "cp", "ns", "čk", "lẓ")
SIMPLE_ROOTS = (*UNITS, "j")  # 0..10
HUNDRED_ROOT = "gz"
# TNX (multiples of ten): Vx-Cs in Slot VII, degrees one through nine.
TNX_VOWELS = ("", "a", "ä", "e", "i", "ëi", "ö", "o", "ü", "u")
NUMERAL_CASES = {"THM": "a", "PAR": "ui"}
# Ch.9.1 neutral-effect monadic referentials; named graph nodes are NOT these.
REFERENTIAL_ROOTS = {"1m": "l", "2m": "s", "ma": "m", "mi": "z"}
REFERENTIAL_CASES = {"THM": "a", "ERG": "o", "ABS": "e", "INS": "ä"}
NUMERAL_MEANING = "BSC stem 1 set/cardinality, not a context-free integer constant"


@dataclass(frozen=True)
class Numeral:
    value: int
    case: str = "THM"
    shortcut: bool = False


@dataclass(frozen=True)
class Referential:
    referent: str
    case: str = "ERG"


@dataclass(frozen=True)
class Analysis:
    kind: str
    surface: str
    semantics: dict
    slots: dict
    sources: tuple[str, ...]
    scope: str = "SUBSET_GRAMMAR_ONLY_NOT_WHOLE_ITHKUIL_CERTIFICATION"
    model_mastery: bool = False


def _validate_numeral(value: int, case: str, shortcut: bool) -> None:
    if type(value) is not int or not 0 <= value <= 100:
        raise ConstructionError("NUMERAL_OUTSIDE_ATTESTED_ZERO_TO_HUNDRED")
    if not isinstance(case, str) or case not in NUMERAL_CASES:
        raise ConstructionError("NUMERAL_CASE_OUTSIDE_THM_PAR_SUBSET")
    if type(shortcut) is not bool:
        raise ConstructionError("SHORTCUT_MUST_BE_BOOLEAN")


def _assemble(value: int, case: str, shortcut: bool) -> tuple[str, dict]:
    ones, tens = value % 10, value // 10
    root = HUNDRED_ROOT if value == 100 else (
        SIMPLE_ROOTS[value] if value <= 10 else UNITS[ones]
    )
    # Ch.3.10: w+a elides default Slot IV BSC/STA/EXS -a-
    # and Slot VI Ca -l- (default configuration etc).
    initial = "wa" + root if shortcut else root + "al"
    tnx = TNX_VOWELS[tens] + "rs" if 11 <= value <= 99 else ""
    slots = {
        "I_II": "wa" if shortcut else "unmarked stem-1 PRC",
        "III_root": root,
        "IV_BSC_STA_EXS": "elided" if shortcut else "a",
        "VI_default_Ca": "elided" if shortcut else "l",
        "VII_TNX": tnx or "absent",
        "IX_case": NUMERAL_CASES[case],
        "stem": 1,
        "specification": "BSC",
        "function": "STA",
    }
    return initial + tnx + NUMERAL_CASES[case], slots


def generate_numeral(form: Numeral) -> Analysis:
    """Render source-attested stem-1/BSC numeral slot structure."""
    if not isinstance(form, Numeral):
        raise ConstructionError("NUMERAL_TYPED_INPUT_REQUIRED")
    _validate_numeral(form.value, form.case, form.shortcut)
    surface, slots = _assemble(form.value, form.case, form.shortcut)
    return Analysis(
        kind="numeral", surface=surface,
        semantics={"value": form.value, "case": form.case,
                   "shortcut": form.shortcut, "meaning": NUMERAL_MEANING},
        slots=slots, sources=(NUMBER_SOURCE, MORPHOLOGY_SOURCE, CASE_SOURCE),
    )


def parse_numeral(surface: str) -> Analysis:
    """Independent slot-by-slot analysis, not generated-form dictionary lookup."""
    if not isinstance(surface, str) or not surface:
        raise ConstructionError("NUMERAL_SURFACE_REQUIRED")
    if (unicodedata.normalize("NFC", surface) != surface
            or surface != surface.lower()
            or any(char.isspace() for char in surface)):
        raise ConstructionError("NONCANONICAL_ROMANIZATION")

    case = next((name for name, suffix in sorted(
        NUMERAL_CASES.items(), key=lambda pair: -len(pair[1])
    ) if surface.endswith(suffix)), None)
    if case is None:
        raise ConstructionError("UNKNOWN_OR_MISSING_NUMERAL_CASE")
    body = surface[:-len(NUMERAL_CASES[case])]
    degree = 0
    if body.endswith("rs"):
        affixless = body[:-2]
        # Longer multigraph vowel first (TNX/5 uses ëi).
        for index, vowel in sorted(enumerate(TNX_VOWELS), key=lambda x: -len(x[1])):
            if index and affixless.endswith(vowel):
                degree = index
                body = affixless[:-len(vowel)]
                break
        if degree == 0:
            raise ConstructionError("TNX_REQUIRES_VALID_DEGREE_VOWEL")

    shortcut = body.startswith("wa")
    if shortcut:
        root = body[2:]
    else:
        if not body.endswith("al"):
            raise ConstructionError("NUMERAL_SLOTS_IV_VI_MISSING")
        root = body[:-2]

    if degree:
        if root not in UNITS:
            raise ConstructionError("TNX_REQUIRES_0_TO_9_ROOT")
        value = degree * 10 + UNITS.index(root)
        if not 11 <= value <= 99:
            raise ConstructionError("TNX_VALUE_OUTSIDE_11_TO_99")
    elif root == HUNDRED_ROOT:
        value = 100
    elif root in SIMPLE_ROOTS:
        value = SIMPLE_ROOTS.index(root)
    else:
        raise ConstructionError("NUMERAL_ROOT_UNKNOWN")

    # Only these explicitly supported slot settings are admissible.
    # This comparison checks normalized spelling, not semantic derivation.
    canonical, slots = _assemble(value, case, shortcut)
    if canonical != surface:
        raise ConstructionError("NUMERAL_MORPHOTACTIC_SLOT_ORDER_INVALID")
    return Analysis(
        kind="numeral", surface=surface,
        semantics={"value": value, "case": case,
                   "shortcut": shortcut, "meaning": NUMERAL_MEANING},
        slots=slots, sources=(NUMBER_SOURCE, MORPHOLOGY_SOURCE, CASE_SOURCE),
    )


def generate_referential(form: Referential) -> Analysis:
    """Ch.9.1 C1+VC1: neutral, monadic and single referent only."""
    if not isinstance(form, Referential):
        raise ConstructionError("REFERENTIAL_TYPED_INPUT_REQUIRED")
    if (not isinstance(form.referent, str) or not isinstance(form.case, str)
            or form.referent not in REFERENTIAL_ROOTS
            or form.case not in REFERENTIAL_CASES):
        raise ConstructionError("REFERENTIAL_OUTSIDE_NEUTRAL_MONADIC_SUBSET")
    consonant = REFERENTIAL_ROOTS[form.referent]
    vowel = REFERENTIAL_CASES[form.case]
    return Analysis(
        kind="referential", surface=consonant + vowel,
        semantics={"referent": form.referent, "case": form.case,
                   "effect": "neutral", "named_identity": False},
        slots={"C1": consonant, "VC1": vowel},
        sources=(REF_GRAMMAR, CASE_SOURCE),
    )


def parse_referential(surface: str) -> Analysis:
    """Parse one-person neutral-effect C1+VC1 without reusing renderer."""
    if not isinstance(surface, str) or not surface:
        raise ConstructionError("REFERENTIAL_SURFACE_REQUIRED")
    if unicodedata.normalize("NFC", surface) != surface:
        raise ConstructionError("NONCANONICAL_ROMANIZATION")
    consonants = {value: key for key, value in REFERENTIAL_ROOTS.items()}
    vowels = {value: key for key, value in REFERENTIAL_CASES.items()}
    candidates = [
        (consonants[surface[:-len(vowel)]], name)
        for vowel, name in vowels.items()
        if surface.endswith(vowel) and surface[:-len(vowel)] in consonants
    ]
    if len(candidates) != 1:
        raise ConstructionError("REFERENTIAL_NOT_SUPPORTED_OR_AMBIGUOUS")
    referent, case = candidates[0]
    return Analysis(
        kind="referential", surface=surface,
        semantics={"referent": referent, "case": case,
                   "effect": "neutral", "named_identity": False},
        slots={"C1": REFERENTIAL_ROOTS[referent],
               "VC1": REFERENTIAL_CASES[case]},
        sources=(REF_GRAMMAR, CASE_SOURCE),
    )


def historic_integer_bridge(historical_token: str, *,
                            case: str = "THM", shortcut: bool = False) -> dict:
    """Read-only qualified NI projection; does not relabel neural token ABI."""
    if (not isinstance(historical_token, str)
            or not historical_token.startswith("school.number.")):
        raise ConstructionError("NOT_A_HISTORICAL_INTEGER_TOKEN")
    fragment = historical_token.removeprefix("school.number.")
    if (not fragment or len(fragment) > 3
            or not fragment.isascii() or not fragment.isdecimal()
            or str(int(fragment)) != fragment):
        raise ConstructionError("HISTORICAL_INTEGER_TOKEN_NOT_CANONICAL")
    from dataclasses import asdict
    word = generate_numeral(Numeral(int(fragment), case, shortcut))
    return {
        "historical_token": historical_token,
        "historical_semantics": "exact integer " + fragment,
        "review_version": REVIEW_VERSION,
        "ni_mapping_kind": "QUALIFIED_CARDINALITY_NOT_EXACT_SCALAR_EQUIVALENCE",
        "constructed_form": asdict(word),
        "new_lexical_token_admitted": False,
        "legacy_model_token_changed": False,
        "neural_updates": 0,
    }


def main(argv=None) -> None:
    from dataclasses import asdict
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    number = commands.add_parser("number")
    number.add_argument("value", type=int)
    number.add_argument("--case", choices=tuple(NUMERAL_CASES), default="THM")
    number.add_argument("--shortcut", action="store_true")
    parsed = commands.add_parser("parse-number")
    parsed.add_argument("surface")
    referent = commands.add_parser("referent")
    referent.add_argument("value", choices=tuple(REFERENTIAL_ROOTS))
    referent.add_argument("--case", choices=tuple(REFERENTIAL_CASES), default="ERG")
    parsed_ref = commands.add_parser("parse-referent")
    parsed_ref.add_argument("surface")
    args = parser.parse_args(argv)
    try:
        if args.action == "number":
            result = generate_numeral(Numeral(args.value, args.case, args.shortcut))
        elif args.action == "parse-number":
            result = parse_numeral(args.surface)
        elif args.action == "referent":
            result = generate_referential(Referential(args.value, args.case))
        else:
            result = parse_referential(args.surface)
    except ConstructionError as exc:
        parser.error(str(exc))
    print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
