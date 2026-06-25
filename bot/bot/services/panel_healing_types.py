from dataclasses import dataclass


@dataclass(frozen=True)
class PanelHealResult:
    status: str
    key_id: int | None
    user_id: int | None
    server_id: int | None
    email: str | None
    details: str | None = None
