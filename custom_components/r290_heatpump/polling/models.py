from dataclasses import dataclass, field


class RegisterAddressError(RuntimeError):
    """Device returned Modbus exception 02 (illegal data address)."""


class WriteVerificationError(RuntimeError):
    """The requested value was not confirmed by a subsequent device read."""


@dataclass
class Sample:
    value: int | None = None
    received: float | None = None
    received_at: str | None = None
    changed_at: str | None = None
    previous: int | None = None
    error: str | None = None
    attempted_at: str | None = None
    expired: bool = False

    def available(self, now, max_age):
        return (
            self.received is not None
            and not self.error
            and now - self.received <= max_age
        )


@dataclass
class Demand:
    owners: dict = field(default_factory=dict)
    due: float = 0
    blocked_until: float = 0

    @property
    def interval(self):
        return min(v[0] for v in self.owners.values())

    @property
    def priority(self):
        return min(v[1] for v in self.owners.values())

    @property
    def max_age(self):
        return min(v[2] for v in self.owners.values())


@dataclass
class Job:
    unit: int
    start: int
    count: int
    priority: int
    created: float
    future: object
    value: int | None = None
    owners: set = field(default_factory=set)
