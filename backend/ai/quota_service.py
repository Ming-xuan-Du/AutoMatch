
"""PostgreSQL-backed AI extraction quota reservations.

This service does not call an AI provider.
Public AI access remains disabled until API integration
and security validation are completed.
"""

import hashlib
import hmac
import ipaddress
import re

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text, update
from sqlalchemy.exc import SQLAlchemyError

from backend.database.models import AIExtractionAttempt


# All AutoMatch quota reservations use the same lock key.
QUOTA_LOCK_KEY = 814726315009


class AIQuotaUnavailable(Exception):
    """Quota verification could not be completed safely."""


class AIQuotaExceeded(Exception):
    """A configured usage or concurrency limit was reached."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class QuotaLimits:
    visitor_per_hour: int = 3
    global_per_day: int = 30
    global_per_month: int = 200
    max_concurrent: int = 1
    lease_seconds: int = 180

    def __post_init__(self):
        values = (
            self.visitor_per_hour,
            self.global_per_day,
            self.global_per_month,
            self.max_concurrent,
            self.lease_seconds,
        )

        if any(value <= 0 for value in values):
            raise ValueError(
                "AI quota limits must be positive."
            )


def hash_visitor_ip(
    raw_ip: str,
    secret: str,
) -> str:
    """HMAC visitor identity without storing the raw IP.

    The caller must obtain the IP from a trusted source.
    Never trust arbitrary client-supplied proxy headers.
    """

    if len(secret.encode("utf-8")) < 32:
        raise AIQuotaUnavailable(
            "Visitor identity protection is not configured."
        )

    try:
        address = ipaddress.ip_address(raw_ip)
    except ValueError:
        raise AIQuotaUnavailable(
            "A valid visitor identity is unavailable."
        ) from None

    if (
        isinstance(address, ipaddress.IPv6Address)
        and address.ipv4_mapped is not None
    ):
        address = address.ipv4_mapped

    return hmac.new(
        secret.encode("utf-8"),
        address.compressed.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def _check_database(session) -> None:
    """Require PostgreSQL and READ COMMITTED isolation."""

    bind = session.get_bind()

    if bind.dialect.name != "postgresql":
        raise AIQuotaUnavailable(
            "AI quotas require PostgreSQL."
        )

    isolation = session.connection().get_isolation_level()

    if isolation.upper() != "READ COMMITTED":
        raise AIQuotaUnavailable(
            "AI quotas require READ COMMITTED isolation."
        )


def _count_attempts(session, *conditions) -> int:
    result = session.scalar(
        select(func.count(AIExtractionAttempt.id))
        .where(*conditions)
    )

    return int(result or 0)


def reserve_ai_extraction(
    session_factory,
    visitor_hash: str,
    *,
    limits: QuotaLimits = QuotaLimits(),
) -> int:
    """Atomically reserve one AI extraction request.

    Returns the persistent reservation ID.

    All reservations must use this service to enforce
    global quotas correctly across application workers.
    """

    if re.fullmatch(
        r"[0-9a-f]{64}",
        visitor_hash,
    ) is None:
        raise AIQuotaUnavailable(
            "Visitor identity is unavailable."
        )

    try:
        with session_factory.begin() as session:
            _check_database(session)

            # Prevent indefinite waits for quota locks.
            session.execute(
                text("SET LOCAL lock_timeout = '3s'")
            )

            # Serialize the check-and-insert operation.
            session.execute(
                text(
                    "SELECT pg_advisory_xact_lock(:lock_key)"
                ),
                {"lock_key": QUOTA_LOCK_KEY},
            )

            # Read the database clock after acquiring
            # the lock, avoiding worker clock differences.
            now = session.scalar(
                select(func.clock_timestamp())
            ).astimezone(timezone.utc)

            hour_start = now - timedelta(hours=1)

            day_start = now.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )

            month_start = day_start.replace(day=1)

            active_count = _count_attempts(
                session,
                AIExtractionAttempt.status == "reserved",
                AIExtractionAttempt.lease_expires_at > now,
            )

            if active_count >= limits.max_concurrent:
                raise AIQuotaExceeded("concurrency")

            visitor_count = _count_attempts(
                session,
                AIExtractionAttempt.visitor_hash
                == visitor_hash,
                AIExtractionAttempt.created_at
                >= hour_start,
            )

            if visitor_count >= limits.visitor_per_hour:
                raise AIQuotaExceeded("visitor_hour")

            daily_count = _count_attempts(
                session,
                AIExtractionAttempt.created_at
                >= day_start,
            )

            if daily_count >= limits.global_per_day:
                raise AIQuotaExceeded("global_day")

            monthly_count = _count_attempts(
                session,
                AIExtractionAttempt.created_at
                >= month_start,
            )

            if monthly_count >= limits.global_per_month:
                raise AIQuotaExceeded("global_month")

            reservation = AIExtractionAttempt(
                visitor_hash=visitor_hash,
                created_at=now,
                lease_expires_at=(
                    now
                    + timedelta(seconds=limits.lease_seconds)
                ),
                status="reserved",
            )

            session.add(reservation)
            session.flush()

            reservation_id = reservation.id

        # Returning after the transaction commits means
        # the quota is persisted before any AI call starts.
        return reservation_id

    except SQLAlchemyError as exc:
        raise AIQuotaUnavailable(
            "AI quota storage is unavailable."
        ) from exc


def finish_ai_extraction(
    session_factory,
    reservation_id: int,
    *,
    succeeded: bool,
) -> bool:
    """Mark a reservation completed or failed.

    Failed requests still count toward usage quotas.
    Returns False when the reservation was not pending.
    """

    status = "completed" if succeeded else "failed"

    try:
        with session_factory.begin() as session:
            _check_database(session)

            result = session.execute(
                update(AIExtractionAttempt)
                .where(
                    AIExtractionAttempt.id == reservation_id,
                    AIExtractionAttempt.status == "reserved",
                )
                .values(status=status)
            )

            changed = result.rowcount == 1

        return changed

    except SQLAlchemyError as exc:
        raise AIQuotaUnavailable(
            "AI quota storage is unavailable."
        ) from exc
