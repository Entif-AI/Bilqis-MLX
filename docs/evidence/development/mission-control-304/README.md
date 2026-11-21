# Mission Control semantic release cockpit evidence

Issue #304 adds the read-only semantic release and graph projection cockpit to
the existing Semantic Atlas workspace. The implementation branch started from
`dbc13d3bf48bd5e9b457e42bbd9e33b18ca37d5b` on `main`.

These captures use repository fixtures. They prove renderer behavior and
defensive-state presentation. They do not assert that a live semantic release
or Falkor projection has the fixture values.

The cockpit keeps two evidence layers separate. Canonical release identity comes
from the accepted generation's authenticated Atlas artifact. Projection state is
derived from an exact comparison with durable Akasha materialization receipts.
The UI never treats graph availability as semantic authority.

| File | Proof |
| --- | --- |
| `projection-current.png` | Exact RDF and coverage identities produce `CURRENT`. |
| `projection-stale.png` | A durable receipt with mismatched identities remains visibly `STALE`. |
| `projection-partial.png` | Exact identities with partial coverage remain visibly `PARTIAL`. |
| `projection-missing.png` | No materialization receipt remains visibly `MISSING`. |
| `projection-error.png` | Invalid or unreadable materialization evidence remains visibly `ERROR`. |
| `atlas-dark-comfortable-1440.png` | Desktop dark/comfortable layout. |
| `atlas-light-compact-1440.png` | Desktop light/compact layout. |
| `atlas-dark-comfortable-390.png` | Narrow dark/comfortable layout. |
| `atlas-light-compact-320.png` | Narrow light/compact layout. |
| `atlas-rtl-text-spacing-320.png` | RTL, expanded text spacing, and reduced-motion reflow. |
| `browser-result.json` | Machine-readable browser acceptance receipt. |

The browser run reported zero horizontal overflow and zero axe violations for
the four primary responsive/theme variants. It also reconstructed all five
projection states in a fresh Chromium context. The release view shows held,
IR-only, and implementation-uncovered counts without calling them official
frontier debt. When the accepted Atlas artifact does not carry the full coverage
receipt verdict, `coverage_status` and `frontier_debt` remain explicitly
unavailable rather than inferred from those counts.
