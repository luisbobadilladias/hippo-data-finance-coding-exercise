"""Event schemas and validation.

Each parse_* function takes one raw record (a dict from JSON or CSV)
and returns a typed object, or raises InvalidRecord saying why not.
"""
import math
from dataclasses import dataclass
from datetime import datetime


class InvalidRecord(ValueError):
    """A record that doesn't match the schema. The message is the reason."""


@dataclass(frozen=True)
class Pharmacy:
    npi: str
    chain: str


@dataclass(frozen=True)
class Claim:
    id: str
    npi: str
    ndc: str
    price: float
    quantity: float
    timestamp: datetime

    @property
    def unit_price(self) -> float:
        return self.price / self.quantity


@dataclass(frozen=True)
class Revert:
    id: str
    claim_id: str
    timestamp: datetime


# --- field helpers: each returns a clean value or raises InvalidRecord ---

def _object(raw) -> dict:
    if not isinstance(raw, dict):
        raise InvalidRecord("record is not an object")
    return raw


def _text(raw: dict, field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise InvalidRecord(f"{field}: missing or empty")
    return value


def _number(raw: dict, field: str) -> float:
    value = raw.get(field)
    # bool is a subclass of int in Python, so True would otherwise pass as 1
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidRecord(f"{field}: missing or not a number")
    # Python's json module accepts NaN and Infinity, which would poison averages
    if not math.isfinite(value):
        raise InvalidRecord(f"{field}: not a finite number")
    return float(value)


def _timestamp(raw: dict, field: str) -> datetime:
    value = _text(raw, field)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise InvalidRecord(f"{field}: not an ISO 8601 datetime") from None


# --- public parsers ---

def parse_pharmacy(raw) -> Pharmacy:
    raw = _object(raw)
    # The spec calls this field "id"; the sample CSVs call it "npi". Accept either.
    key = "npi" if "npi" in raw else "id"
    return Pharmacy(npi=_text(raw, key), chain=_text(raw, "chain"))


def parse_claim(raw) -> Claim:
    raw = _object(raw)
    quantity = _number(raw, "quantity")
    if quantity <= 0:
        raise InvalidRecord("quantity: must be greater than 0")
    price = _number(raw, "price")
    if price < 0:
        raise InvalidRecord("price: must not be negative")
    return Claim(
        id=_text(raw, "id"),
        npi=_text(raw, "npi"),
        ndc=_text(raw, "ndc"),
        price=price,
        quantity=quantity,
        timestamp=_timestamp(raw, "timestamp"),
    )


def parse_revert(raw) -> Revert:
    raw = _object(raw)
    return Revert(
        id=_text(raw, "id"),
        claim_id=_text(raw, "claim_id"),
        timestamp=_timestamp(raw, "timestamp"),
    )
