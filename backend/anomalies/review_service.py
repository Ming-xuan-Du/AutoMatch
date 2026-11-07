
"""Human review service for AutoMatch anomaly findings.

Updates only anomaly review state and appends audit events.
Never modifies vehicle inventory.

The caller owns the database transaction.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import (
    AnomalyFlag,
    AnomalyReviewEvent,
    utc_now,
)


VALID_STATUSES = frozenset({
    "pending",
    "valid_issue",
    "false_alarm",
})

MAX_NOTE_LENGTH = 2000

_UNSET = object()


class ReviewNotFoundError(LookupError):
    """Requested anomaly finding does not exist."""


class ReviewValidationError(ValueError):
    """Review update contains invalid information."""


@dataclass(frozen=True)
class ReviewResult:
    flag: AnomalyFlag
    changed: bool


def update_anomaly_review(
    session: Session,
    flag_id: int,
    *,
    review_status: str | object = _UNSET,
    reviewer_note: str | None | object = _UNSET,
) -> ReviewResult:
    """Apply an explicit human review and save its history.

    - Omitted fields remain unchanged.
    - Explicit reviewer_note=None clears the note.
    - Identical updates are idempotent.
    - A real change creates exactly one review event.
    - Status and history update in the same transaction.
    - Caller must commit or rollback.
    """

    if type(flag_id) is not int or flag_id <= 0:
        raise ReviewValidationError(
            "flag_id must be a positive integer"
        )

    if (
        review_status is _UNSET
        and reviewer_note is _UNSET
    ):
        raise ReviewValidationError(
            "At least one review field must be provided"
        )

    if review_status is not _UNSET:
        if (
            not isinstance(review_status, str)
            or review_status not in VALID_STATUSES
        ):
            raise ReviewValidationError(
                "Invalid review status"
            )

    if reviewer_note is not _UNSET:
        if reviewer_note is not None:
            if not isinstance(reviewer_note, str):
                raise ReviewValidationError(
                    "Reviewer note must be text or null"
                )

            reviewer_note = reviewer_note.strip()

            if not reviewer_note:
                raise ReviewValidationError(
                    "Reviewer note cannot be blank"
                )

            if len(reviewer_note) > MAX_NOTE_LENGTH:
                raise ReviewValidationError(
                    "Reviewer note exceeds 2000 characters"
                )

    # PostgreSQL acquires a row-level lock until the
    # transaction commits or rolls back.
    statement = (
        select(AnomalyFlag)
        .where(AnomalyFlag.id == flag_id)
        .with_for_update()
    )

    flag = session.scalar(statement)

    if flag is None:
        raise ReviewNotFoundError(
            f"Anomaly finding {flag_id} does not exist"
        )

    previous_status = flag.review_status
    previous_note = flag.reviewer_note

    new_status = (
        previous_status
        if review_status is _UNSET
        else review_status
    )

    new_note = (
        previous_note
        if reviewer_note is _UNSET
        else reviewer_note
    )

    # A repeated identical request should not add
    # unnecessary review history events.
    if (
        new_status == previous_status
        and new_note == previous_note
    ):
        return ReviewResult(
            flag=flag,
            changed=False,
        )

    changed_at = utc_now()

    flag.review_status = new_status
    flag.reviewer_note = new_note

    if new_status != previous_status:
        flag.reviewed_at = (
            changed_at
            if new_status != "pending"
            else None
        )

    event = AnomalyReviewEvent(
        anomaly_flag_id=flag.id,
        previous_status=previous_status,
        new_status=new_status,
        previous_note=previous_note,
        new_note=new_note,
        changed_at=changed_at,
    )

    session.add(event)

    # Stage review status and history atomically.
    # Do not commit in this service.
    session.flush()

    return ReviewResult(
        flag=flag,
        changed=True,
    )
