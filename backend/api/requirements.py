
"""Customer requirement extraction API.

Public AI calls require an explicit enable flag,
a valid visitor identity, and a PostgreSQL quota
reservation before the AI provider is contacted.
"""

import os

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from backend.ai.extractor import (
    ExtractionInvalidResponse,
    ExtractionTimeout,
    ExtractionUnavailable,
    PersonalInformationDetected,
    check_personal_information,
    extract_requirements,
)
from backend.ai.quota_service import (
    AIQuotaExceeded,
    AIQuotaUnavailable,
    finish_ai_extraction,
    hash_visitor_ip,
    reserve_ai_extraction,
)
from backend.ai.schemas import (
    ExtractRequest,
    ExtractResponse,
)
from backend.database.connection import SessionLocal


router = APIRouter(
    prefix="/api/requirements",
    tags=["requirements"],
)


def get_visitor_address(request: Request) -> str:
    """Read the server-resolved client address.

    Production proxy trust must be configured and
    verified before public AI is enabled.
    Never read untrusted X-Forwarded-For directly.
    """

    if request.client is None:
        raise AIQuotaUnavailable(
            "Visitor identity is unavailable."
        )

    return request.client.host


@router.post(
    "/extract",
    response_model=ExtractResponse,
)
async def extract_customer_requirements(
    request: ExtractRequest,
    http_request: Request,
) -> ExtractResponse:
    """Extract structured vehicle requirements.

    Does not query inventory, recommend vehicles,
    or persist customer statements.
    """

    public_demo = (
        os.getenv("AUTOMATCH_PUBLIC_DEMO", "0").strip()
        == "1"
    )

    reservation_id = None
    succeeded = False

    if public_demo:
        enabled = (
            os.getenv(
                "AUTOMATCH_PUBLIC_AI_ENABLED", "0"
            ).strip()
            == "1"
        )

        provider = os.getenv(
            "AI_PROVIDER", "openai"
        ).strip().lower()

        # Keep public AI disabled unless all required
        # configuration has been explicitly supplied.
        if (
            not enabled
            or provider != "openai"
            or not os.getenv(
                "OPENAI_API_KEY", ""
            ).strip()
        ):
            raise HTTPException(
                status_code=503,
                detail=(
                    "AI extraction is temporarily "
                    "unavailable in the public demo. "
                    "Use manual search."
                ),
            )

        try:
            # Reject recognizable PII before consuming
            # a quota reservation or calling an LLM.
            check_personal_information(
                request.customer_text
            )

            visitor_address = get_visitor_address(
                http_request
            )

            visitor_hash = hash_visitor_ip(
                visitor_address,
                os.getenv(
                    "AUTOMATCH_VISITOR_HASH_SECRET", ""
                ),
            )

            # Synchronous database work must not block
            # the async request event loop.
            reservation_id = await run_in_threadpool(
                reserve_ai_extraction,
                SessionLocal,
                visitor_hash,
            )

        except PersonalInformationDetected as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        except AIQuotaExceeded as exc:
            raise HTTPException(
                status_code=429,
                detail=(
                    "AI usage limit reached. "
                    "Please try again later or use "
                    "manual search."
                ),
            ) from exc

        except AIQuotaUnavailable as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "AI usage protection is unavailable. "
                    "Use manual search."
                ),
            ) from exc

    try:
        result = await extract_requirements(
            request.customer_text
        )

        succeeded = True
        return result

    except PersonalInformationDetected as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except ExtractionUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except ExtractionTimeout as exc:
        raise HTTPException(
            status_code=504,
            detail=str(exc),
        ) from exc

    except ExtractionInvalidResponse as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    finally:
        if reservation_id is not None:
            try:
                finalized = await run_in_threadpool(
                    finish_ai_extraction,
                    SessionLocal,
                    reservation_id,
                    succeeded=succeeded,
                )
            except AIQuotaUnavailable as exc:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "AI usage tracking is unavailable."
                    ),
                ) from exc

            if not finalized:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "AI usage reservation could "
                        "not be finalized."
                    ),
                )
