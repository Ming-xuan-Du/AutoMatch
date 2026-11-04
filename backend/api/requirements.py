
from fastapi import APIRouter, HTTPException

from backend.ai.extractor import (
    ExtractionInvalidResponse,
    ExtractionTimeout,
    ExtractionUnavailable,
    PersonalInformationDetected,
    extract_requirements,
)
from backend.ai.schemas import (
    ExtractRequest,
    ExtractResponse,
)


router = APIRouter(
    prefix="/api/requirements",
    tags=["requirements"],
)


@router.post(
    "/extract",
    response_model=ExtractResponse,
)
async def extract_customer_requirements(
    request: ExtractRequest,
) -> ExtractResponse:
    """
    Extract structured customer requirements.

    Does not query the inventory database,
    recommend vehicles, or persist conversations.
    """

    try:
        return await extract_requirements(
            request.customer_text
        )

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
