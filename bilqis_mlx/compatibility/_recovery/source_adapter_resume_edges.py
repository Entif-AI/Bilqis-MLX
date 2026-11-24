"""Enumerable one-way provider edges accepted for historical BAMF resume."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceProviderResumeEdge:
    edge_id: str
    adapter_id: str
    admitted_implementation_sha256: str
    current_implementation_sha256: str
    rule: str


SUPPORTED_SOURCE_PROVIDER_RESUME_EDGES = (
    SourceProviderResumeEdge(
        "grade-a-1324082-to-current", "source.micro.predicates/v1",
        "f8e5aec9398538adc633deabe9c41c485e69a96044b9b86a5f1075ce6e201778",
        "7f05ec04d200d7394f32ed1811a3d9a47ce4cdb9267692bf558453e81e9fb04a",
        "grade-a-1324082"),
    SourceProviderResumeEdge(
        "grade-a-accepted-to-current", "source.micro.predicates/v1",
        "c451c3e6bf5ab538450c691d504230036b9a729ddfc67b53163c6a1f106d62a9",
        "7f05ec04d200d7394f32ed1811a3d9a47ce4cdb9267692bf558453e81e9fb04a",
        "cohort-bound"),
    SourceProviderResumeEdge(
        "grade-a-accepted-to-provenance", "source.micro.predicates/v1",
        "c451c3e6bf5ab538450c691d504230036b9a729ddfc67b53163c6a1f106d62a9",
        "622d963b3a6c9846701e895bcdece1558eb450a92f2e0e5d757a4b3729dd5990",
        "cohort-bound"),
    SourceProviderResumeEdge(
        "grade-a-current-to-provenance", "source.micro.predicates/v1",
        "7f05ec04d200d7394f32ed1811a3d9a47ce4cdb9267692bf558453e81e9fb04a",
        "622d963b3a6c9846701e895bcdece1558eb450a92f2e0e5d757a4b3729dd5990",
        "cohort-bound"),
    SourceProviderResumeEdge(
        "grade-a-1324082-to-provenance", "source.micro.predicates/v1",
        "f8e5aec9398538adc633deabe9c41c485e69a96044b9b86a5f1075ce6e201778",
        "622d963b3a6c9846701e895bcdece1558eb450a92f2e0e5d757a4b3729dd5990",
        "grade-a-1324082"),
    SourceProviderResumeEdge(
        "boolean-connectives-mainline-to-current",
        "source.micro.boolean-connectives/v1",
        "8103a38b7668cabc685c713d69426a064b3b7eabb6322886c75ab1ba14ad60de",
        "67d701119c3569e0400b94ee7a2418e2143751e37974b1b60d347940428f3e8e",
        "cohort-bound"),
    SourceProviderResumeEdge(
        "boolean-connectives-issue1566-pre-structure-to-current",
        "source.micro.boolean-connectives/v1",
        "4848d0a704b47abb90d9ff4d67fc1210ba265a5561294566caec673b87d605dd",
        "67d701119c3569e0400b94ee7a2418e2143751e37974b1b60d347940428f3e8e",
        "cohort-bound"),
    SourceProviderResumeEdge(
        "boolean-composite-mainline-to-current",
        "source.micro.boolean-composite/v1",
        "72e432371bb88ef7beb735ed53ae63a9fd5c16b012a3185782a19b2ee03e3e86",
        "f61710669f09655130670eab9f805d992658594bd75b58f1a580851ccd6421a0",
        "cohort-bound"),
    SourceProviderResumeEdge(
        "boolean-composite-issue1566-pre-structure-to-current",
        "source.micro.boolean-composite/v1",
        "b13c21ff286e77a629cb5be5e25c62986997c1eaca78478381b43b842a174e10",
        "f61710669f09655130670eab9f805d992658594bd75b58f1a580851ccd6421a0",
        "cohort-bound"),
    SourceProviderResumeEdge(
        "boolean-identification-accepted-to-mainline",
        "source.micro.boolean-identification/v1",
        "6399dae052a289d46063df0e897e14f1392e2f1b99e90c2ae791fda9a8246743",
        "811ed2ad7708e6a7ce3a72fb20d92ea8fcc1df51aae45afc01e711fea07d18c6",
        "cohort-bound"),
    SourceProviderResumeEdge(
        "boolean-identification-pre-r15-to-mainline",
        "source.micro.boolean-identification/v1",
        "1404c511d7b5eab19025726d5c4c98073250cc0c75cf37b185344da92060edee",
        "811ed2ad7708e6a7ce3a72fb20d92ea8fcc1df51aae45afc01e711fea07d18c6",
        "cohort-bound"),
    SourceProviderResumeEdge(
        "boolean-identification-accepted-to-current",
        "source.micro.boolean-identification/v1",
        "6399dae052a289d46063df0e897e14f1392e2f1b99e90c2ae791fda9a8246743",
        "8425b3e50e4ddd974ce2dd4a77dc9d6c9a329acdbf35a429924a13cb9ebb433c",
        "cohort-bound"),
    SourceProviderResumeEdge(
        "boolean-identification-pre-r15-to-current",
        "source.micro.boolean-identification/v1",
        "1404c511d7b5eab19025726d5c4c98073250cc0c75cf37b185344da92060edee",
        "8425b3e50e4ddd974ce2dd4a77dc9d6c9a329acdbf35a429924a13cb9ebb433c",
        "cohort-bound"),
    SourceProviderResumeEdge(
        "boolean-identification-mainline-to-current",
        "source.micro.boolean-identification/v1",
        "811ed2ad7708e6a7ce3a72fb20d92ea8fcc1df51aae45afc01e711fea07d18c6",
        "8425b3e50e4ddd974ce2dd4a77dc9d6c9a329acdbf35a429924a13cb9ebb433c",
        "cohort-bound"),
    SourceProviderResumeEdge(
        "boolean-identification-issue1566-pre-structure-to-current",
        "source.micro.boolean-identification/v1",
        "7c39ee7c03af5ed2ad48a71efdddc5e4daddca9e76acb7f3e28a05ac891aa54c",
        "8425b3e50e4ddd974ce2dd4a77dc9d6c9a329acdbf35a429924a13cb9ebb433c",
        "cohort-bound"),
    SourceProviderResumeEdge(
        "numeric-accepted-to-current", "source.finite-numeric/v2",
        "2758cf678e9d2a45f3f5a1b5edd85d5ae513e54506c0d98853b9402b91572754",
        "788978ebb80d2349f6aa91e994f45d2ce32c154040f5ab5b17d8502a8d6dfa10",
        "numeric-modular"),
    SourceProviderResumeEdge(
        "numeric-modular-to-current", "source.finite-numeric/v2",
        "a52f346478852775053f07a79342e5a9e9266bc64a2df6fe953d6a64881c8b7d",
        "788978ebb80d2349f6aa91e994f45d2ce32c154040f5ab5b17d8502a8d6dfa10",
        "numeric-modular"),
    SourceProviderResumeEdge(
        "numeric-pre-r20-to-current", "source.finite-numeric/v2",
        "621257de25895cc5cfcf0b9730c43fbe04260a3aa68732cfcc41a43988cd8141",
        "788978ebb80d2349f6aa91e994f45d2ce32c154040f5ab5b17d8502a8d6dfa10",
        "numeric-modular"),
    SourceProviderResumeEdge(
        "numeric-accepted-to-provenance", "source.finite-numeric/v2",
        "2758cf678e9d2a45f3f5a1b5edd85d5ae513e54506c0d98853b9402b91572754",
        "06a517b9f1272b90233f0ac28ae98458a3a130bf9069e78202b58b84baf2c4cb",
        "numeric-modular"),
    SourceProviderResumeEdge(
        "numeric-modular-to-provenance", "source.finite-numeric/v2",
        "a52f346478852775053f07a79342e5a9e9266bc64a2df6fe953d6a64881c8b7d",
        "06a517b9f1272b90233f0ac28ae98458a3a130bf9069e78202b58b84baf2c4cb",
        "numeric-modular"),
    SourceProviderResumeEdge(
        "numeric-pre-r20-to-provenance", "source.finite-numeric/v2",
        "621257de25895cc5cfcf0b9730c43fbe04260a3aa68732cfcc41a43988cd8141",
        "06a517b9f1272b90233f0ac28ae98458a3a130bf9069e78202b58b84baf2c4cb",
        "numeric-modular"),
    SourceProviderResumeEdge(
        "numeric-current-to-provenance", "source.finite-numeric/v2",
        "788978ebb80d2349f6aa91e994f45d2ce32c154040f5ab5b17d8502a8d6dfa10",
        "06a517b9f1272b90233f0ac28ae98458a3a130bf9069e78202b58b84baf2c4cb",
        "numeric-modular"),
)
