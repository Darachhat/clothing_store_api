"""Payment Gateway (ABA PayWay) configuration endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps.database import get_db
from app.core.deps import require_system_admin
from app.schemas.base_schema import RESPONSE_ENVELOPE
from app.schemas.payment_gateway_schema import (
    PAYMENT_GATEWAY_CONFIG_SCHEMA,
    PAYMENT_GATEWAY_TEST_RESPONSE_SCHEMA,
    PAYMENT_GATEWAY_UPDATE_SCHEMA,
)
from app.services.payment_gateway_service import PAYMENT_GATEWAY_SERVICE

router = APIRouter(prefix="/settings/payment-gateway", tags=["Payment Gateway Configuration"])


@router.get(
    "",
    response_model=RESPONSE_ENVELOPE[PAYMENT_GATEWAY_CONFIG_SCHEMA],
    dependencies=[Depends(require_system_admin)],
)
def get_payment_gateway_config(
    db: Session = Depends(get_db),
):
    """Retrieve current Payment Gateway (ABA PayWay) database configuration."""
    cfg = PAYMENT_GATEWAY_SERVICE.get_gateway_config(db=db)
    return RESPONSE_ENVELOPE.success(
        data=cfg,
        message="Payment gateway configuration retrieved successfully.",
    )


@router.put(
    "",
    response_model=RESPONSE_ENVELOPE[PAYMENT_GATEWAY_CONFIG_SCHEMA],
    dependencies=[Depends(require_system_admin)],
)
def update_payment_gateway_config(
    body: PAYMENT_GATEWAY_UPDATE_SCHEMA,
    db: Session = Depends(get_db),
):
    """Update Payment Gateway (ABA PayWay) configuration and credentials."""
    updated = PAYMENT_GATEWAY_SERVICE.update_gateway_config(db=db, data=body)
    return RESPONSE_ENVELOPE.success(
        data=updated,
        message="Payment gateway configuration updated successfully.",
    )


@router.post(
    "/test",
    response_model=RESPONSE_ENVELOPE[PAYMENT_GATEWAY_TEST_RESPONSE_SCHEMA],
    dependencies=[Depends(require_system_admin)],
)
async def test_payment_gateway_connection(
    db: Session = Depends(get_db),
):
    """Test connectivity and signature validation against ABA PayWay gateway."""
    res = await PAYMENT_GATEWAY_SERVICE.test_gateway_connection(db=db)
    return RESPONSE_ENVELOPE.success(
        data=res,
        message="Payment gateway test completed.",
    )

