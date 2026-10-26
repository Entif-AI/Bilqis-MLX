"""Machine-readable failures at the semantic compiler boundary."""


class ProfileError(ValueError):
    """A stable reason code with deterministic, source-addressable details."""

    def __init__(self, code: str, *details: str) -> None:
        self.code = code
        self.details = tuple(sorted(details))
        super().__init__(f"{code}: {'; '.join(self.details)}")

    def as_dict(self) -> dict:
        return {"code": self.code, "details": list(self.details)}
