"""Payment service — orchestrates ABA PayWay flows.

Responsibilities:
- Generate unique tran_id (max 20 chars)
- Create KHQR via PayWay Purchase API
- Build base64 QR image from qr_string for the POS
- refresh_status: call Check Transaction, idempotently complete the Sale on APPROVED
- cancel: call Close Transaction, mark transaction CANCELLED
"""
from __future__ import annotations

import base64
import io
import random
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enum.common_enum import (
    CURRENCY_ENUM
    , PAYMENT_CHANNEL_ENUM
    , PAYMENT_METHOD_ENUM
    , PAYMENT_PROVIDER_ENUM
    , PAYMENT_STATUS_ENUM
    , SALE_STATUS_ENUM
)
from app.core.exceptions import (
    BAD_GATEWAY_EXCEPTION
    , CONFLICT_EXCEPTION
    , NOT_FOUND_EXCEPTION
)
from app.core.logging import get_logger
from app.models import PaymentTransaction, Sale
from app.schemas.payment_schema import (
    PAYMENT_KHQR_CREATE_REQUEST_SCHEMA
    , PAYMENT_PURCHASE_FORM_REQUEST_SCHEMA
    , PAYMENT_PURCHASE_FORM_RESPONSE_SCHEMA
    , PAYMENT_TRANSACTION_RESPONSE_SCHEMA
)
from app.services.payway import map_payway_status, payway_client
from app.services.sale_service import SALE_SERVICE

logger = get_logger(__name__)


# ── tran_id generation ───────────────────────────────────────────────────────

def _generate_tran_id() -> str:
    """Return a unique tran_id <= 20 chars.
    Format: S<10-char base36 epoch millis><4 random alphanum>
    e.g. S0LWKA1BX2Q3F8AB  (16 chars)
    """
    epoch_36 = ""
    n = int(datetime.now(timezone.utc).timestamp() * 1000)
    chars = string.digits + string.ascii_uppercase
    while n:
        epoch_36 = chars[n % 36] + epoch_36
        n //= 36
    epoch_36 = epoch_36[:10].zfill(10)
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"S{epoch_36}{suffix}"


# ── QR image builder ─────────────────────────────────────────────────────────

def _qr_to_data_url(qr_string: str) -> str:
    """Render qr_string as a PNG data URL using the qrcode library."""
    try:
        import qrcode  # type: ignore[import]
        from qrcode.image.pil import PilImage  # type: ignore[import]

        qr = qrcode.QRCode(
            version          = None
            , error_correction = qrcode.constants.ERROR_CORRECT_M
            , box_size         = 8
            , border           = 4
        )
        qr.add_data(qr_string)
        qr.make(fit=True)
        img: PilImage = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception as exc:
        logger.warning(f"[PAYMENT_SERVICE] QR image build failed: {exc}")
        return ""


# ── Service ──────────────────────────────────────────────────────────────────

class PAYMENT_SERVICE:
    """Service orchestrating digital payment transactions, PayWay KHQR flows, and async pushbacks."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _callback_urls(self, tran_id: str) -> Tuple[str, str, str]:
        """Return (return_url, cancel_url, continue_success_url)."""
        base = (settings.PAYWAY_CALLBACK_BASE_URL or "https://example.com").rstrip("/")
        return (
            f"{base}/api/payments/aba/pushback"
            , f"{base}/api/payments/aba/pushback"
            , f"{base}/api/payments/aba/pushback"
        )

    async def create_khqr_for_sale(
        self
        , sale_id    : UUID
        , created_by : UUID
    ) -> PaymentTransaction:
        """Create ABA KHQR for a DRAFT sale."""
        sale: Optional[Sale] = await self.db.get(Sale, sale_id)
        if not sale:
            raise NOT_FOUND_EXCEPTION("Sale not found")
        if sale.sale_status != SALE_STATUS_ENUM.DRAFT.value:
            raise CONFLICT_EXCEPTION(f"Sale is already {sale.sale_status}")

        existing_result = await self.db.execute(
            select(PaymentTransaction.id).where(
                PaymentTransaction.sale_id == sale_id
                , PaymentTransaction.status == PAYMENT_STATUS_ENUM.PENDING.value
            )
        )
        for stale_id in existing_result.scalars().all():
            stale = await self.refresh_status(stale_id)
            if stale.status == "APPROVED":
                raise CONFLICT_EXCEPTION("The previous QR was already paid")
            if stale.status == PAYMENT_STATUS_ENUM.PENDING.value:
                try:
                    await payway_client.close_transaction(stale.tran_id)
                except Exception as exc:
                    logger.warning(f"[PAYMENT_SERVICE] Close stale tx error (continuing): {exc}")
                stale.status = "CANCELLED"
                logger.info(f"[PAYMENT_SERVICE] Cancelled stale tx {stale.tran_id}")

        tran_id = _generate_tran_id()
        amount  = float(sale.total)

        try:
            aba_resp = await payway_client.create_khqr(
                tran_id     = tran_id
                , amount_usd = amount
                , item_name  = f"Sale {sale.invoice_number or 'Order'}"
            )
        except Exception as exc:
            logger.error(f"[PAYMENT_SERVICE] PayWay generate-qr error: {exc}")
            raise BAD_GATEWAY_EXCEPTION(f"ABA PayWay error: {exc}") from exc

        qr_string    = aba_resp.get("qrString") or aba_resp.get("qr_string") or ""
        qr_image_url = aba_resp.get("qrImage") or aba_resp.get("qr_image") or ""
        deeplink     = aba_resp.get("abapay_deeplink") or ""

        safe_resp = {k: v for k, v in aba_resp.items() if k not in ("hash",)}

        tx = PaymentTransaction(
            provider        = PAYMENT_PROVIDER_ENUM.ABA_PAYWAY.value
            , tran_id        = tran_id
            , sale_id        = sale_id
            , channel        = PAYMENT_CHANNEL_ENUM.POS.value
            , payment_option = "abapay_khqr"
            , amount         = amount
            , currency       = CURRENCY_ENUM.USD.value
            , status         = PAYMENT_STATUS_ENUM.PENDING.value
            , qr_string      = qr_string
            , checkout_url   = deeplink
            , expires_at     = datetime.now(timezone.utc)
            + timedelta(minutes=settings.PAYWAY_QR_LIFETIME_MINUTES)
            , last_response  = safe_resp
            , created_by     = created_by
        )
        self.db.add(tx)
        await self.db.flush()
        await self.db.refresh(tx)

        tx.qr_image = _qr_to_data_url(qr_string) or qr_image_url  # type: ignore[attr-defined]
        logger.info(f"[PAYMENT_SERVICE] KHQR created tran_id={tran_id} sale={sale_id}")
        return tx

    async def create_purchase_for_sale(
        self
        , sale_id        : UUID
        , payment_option : str
        , created_by     : UUID
    ) -> Tuple[str, Dict[str, str], PaymentTransaction]:
        """Create an ABA PayWay purchase transaction for checkout modal / bottom sheet."""
        sale: Optional[Sale] = await self.db.get(Sale, sale_id)
        if not sale:
            raise NOT_FOUND_EXCEPTION("Sale not found")
        if sale.sale_status != SALE_STATUS_ENUM.DRAFT.value:
            raise CONFLICT_EXCEPTION(f"Sale is already {sale.sale_status}")

        existing_result = await self.db.execute(
            select(PaymentTransaction.id).where(
                PaymentTransaction.sale_id == sale_id
                , PaymentTransaction.status == PAYMENT_STATUS_ENUM.PENDING.value
            )
        )
        for stale_id in existing_result.scalars().all():
            stale = await self.refresh_status(stale_id)
            if stale.status == "APPROVED":
                raise CONFLICT_EXCEPTION("The previous payment was already completed")
            if stale.status == PAYMENT_STATUS_ENUM.PENDING.value:
                try:
                    await payway_client.close_transaction(stale.tran_id)
                except Exception as exc:
                    logger.warning(f"[PAYMENT_SERVICE] Close stale tx error (continuing): {exc}")
                stale.status = "CANCELLED"
                logger.info(f"[PAYMENT_SERVICE] Cancelled stale tx {stale.tran_id}")

        tran_id = _generate_tran_id()
        amount  = float(sale.total)

        action_url, form_data = payway_client.build_purchase_form_data(
            tran_id          = tran_id
            , amount_usd     = amount
            , payment_option = payment_option or ""
            , item_name      = f"Sale {sale.invoice_number or 'Order'}"
        )

        safe_form = {k: v for k, v in form_data.items() if k not in ("hash",)}

        tx = PaymentTransaction(
            provider        = PAYMENT_PROVIDER_ENUM.ABA_PAYWAY.value
            , tran_id        = tran_id
            , sale_id        = sale_id
            , channel        = f"{PAYMENT_CHANNEL_ENUM.POS.value}_MODAL"
            , payment_option = payment_option or "all"
            , amount         = amount
            , currency       = CURRENCY_ENUM.USD.value
            , status         = PAYMENT_STATUS_ENUM.PENDING.value
            , qr_string      = None
            , checkout_url   = action_url
            , expires_at     = datetime.now(timezone.utc)
            + timedelta(minutes=settings.PAYWAY_QR_LIFETIME_MINUTES)
            , last_response  = {"form_data": safe_form}
            , created_by     = created_by
        )
        self.db.add(tx)
        await self.db.flush()
        await self.db.refresh(tx)

        logger.info(
            f"[PAYMENT_SERVICE] Purchase form created tran_id={tran_id} sale={sale_id} option={payment_option}"
        )
        return action_url, form_data, tx

    async def refresh_status(self, tx_id: UUID) -> PaymentTransaction:
        """Check ABA for the latest status. On APPROVED, complete the sale."""
        result = await self.db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.id == tx_id)
            .with_for_update()
        )
        tx: Optional[PaymentTransaction] = result.scalar_one_or_none()
        if not tx:
            raise NOT_FOUND_EXCEPTION("Transaction not found")

        if tx.status not in (PAYMENT_STATUS_ENUM.PENDING.value,):
            return tx

        try:
            aba_resp = await payway_client.check_transaction(tx.tran_id)
        except Exception as exc:
            logger.warning(f"[PAYMENT_SERVICE] Check transaction error: {exc}")
            return tx

        safe_resp = {k: v for k, v in aba_resp.items() if k not in ("hash",)}
        tx.last_response = safe_resp

        new_status, apv = map_payway_status(aba_resp)
        tx.status = new_status
        if apv:
            tx.apv = apv

        if new_status == "APPROVED":
            tx.paid_at = datetime.now(timezone.utc)

            payment_method_name = PAYMENT_METHOD_ENUM.CARD.value if tx.payment_option == "cards" else "ABA_KHQR"
            card_info = ""
            try:
                detail_resp = await payway_client.get_transaction_detail(tx.tran_id)
                detail_data = detail_resp.get("data") or {}
                pay_type    = (detail_data.get("payment_type") or "").upper()
                payer_acc   = detail_data.get("payer_account") or ""
                if pay_type in ("VISA", "MC", "JCB", "CUP") or tx.payment_option == "cards":
                    payment_method_name = PAYMENT_METHOD_ENUM.CARD.value
                    card_info           = f"{pay_type} {payer_acc}".strip()
                elif pay_type in ("ABA PAY", "KHQR"):
                    payment_method_name = "ABA_KHQR"

                safe_detail = {k: v for k, v in detail_data.items() if k not in ("hash",)}
                if isinstance(tx.last_response, dict):
                    tx.last_response = {**tx.last_response, "detail": safe_detail}
            except Exception as detail_exc:
                logger.warning(f"[PAYMENT_SERVICE] Could not fetch detail: {detail_exc}")

            if tx.sale_id:
                sale_result = await self.db.execute(
                    select(Sale).where(Sale.id == tx.sale_id).with_for_update()
                )
                sale: Optional[Sale] = sale_result.scalar_one_or_none()
                if sale and sale.sale_status == SALE_STATUS_ENUM.DRAFT.value:
                    svc = SALE_SERVICE(self.db)
                    ref_text = tx.apv or tx.tran_id
                    if card_info:
                        ref_text = f"{ref_text} ({card_info})"

                    await svc.complete_sale(
                        sale
                        , payments = [
                            {
                                "payment_method": payment_method_name
                                , "amount": float(tx.amount)
                                , "reference_number": ref_text
                            }
                        ]
                    )
                    logger.info(
                        f"[PAYMENT_SERVICE] Sale {sale.id} completed via {payment_method_name} tran_id={tx.tran_id}"
                    )

                    try:
                        from app.services.product_service import PRODUCT_SERVICE

                        await PRODUCT_SERVICE.increment_inventory_version(self.db)
                        if sale.promotion_id and (sale.notes or "").startswith("[ONLINE STORE]"):
                            from app.services.misc_service import PROMOTION_SERVICE

                            await PROMOTION_SERVICE(self.db).record_usage(sale.promotion_id)
                    except Exception as post_exc:
                        logger.warning(f"[PAYMENT_SERVICE] Post-completion bookkeeping failed: {post_exc}")

                    try:
                        from app.tasks.notification_tasks import send_telegram  # noqa
                        send_telegram.delay(
                            f"✅ *ABA PayWay Payment APPROVED*\n"
                            f"Method: `{payment_method_name}` {card_info}\n"
                            f"Invoice: `{sale.invoice_number}`\n"
                            f"Amount: `${float(tx.amount):.2f}`\n"
                            f"APV: `{tx.apv}`\n"
                            f"Tran ID: `{tx.tran_id}`"
                        )
                    except Exception as tg_exc:
                        logger.warning(f"[PAYMENT_SERVICE] Telegram notify failed: {tg_exc}")

        elif new_status in ("DECLINED", "CANCELLED"):
            logger.info(f"[PAYMENT_SERVICE] tran_id={tx.tran_id} is {new_status}")

        await self.db.flush()
        return tx

    async def cancel(self, tx_id: UUID) -> PaymentTransaction:
        """Cancel a PENDING QR — call Close Transaction then mark CANCELLED."""
        result = await self.db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.id == tx_id)
            .with_for_update()
        )
        tx: Optional[PaymentTransaction] = result.scalar_one_or_none()
        if not tx:
            raise NOT_FOUND_EXCEPTION("Transaction not found")

        if tx.status != PAYMENT_STATUS_ENUM.PENDING.value:
            raise CONFLICT_EXCEPTION(f"Cannot cancel a transaction in status {tx.status}")

        tx = await self.refresh_status(tx_id)
        if tx.status != PAYMENT_STATUS_ENUM.PENDING.value:
            raise CONFLICT_EXCEPTION(f"Payment is already {tx.status}; cannot cancel")

        try:
            await payway_client.close_transaction(tx.tran_id)
        except Exception as exc:
            logger.warning(f"[PAYMENT_SERVICE] Close transaction error (continuing): {exc}")

        tx.status = "CANCELLED"
        await self.db.flush()
        return tx

    async def create_khqr_payload(
        self
        , payload    : PAYMENT_KHQR_CREATE_REQUEST_SCHEMA
        , created_by : UUID
    ) -> PaymentTransaction:
        """Create ABA KHQR using structured PAYMENT_KHQR_CREATE_REQUEST_SCHEMA."""
        return await self.create_khqr_for_sale(
            sale_id    = payload.sale_id
            , created_by = created_by
        )

    async def create_purchase_payload(
        self
        , payload    : PAYMENT_PURCHASE_FORM_REQUEST_SCHEMA
        , created_by : UUID
    ) -> Tuple[str, Dict[str, str], PaymentTransaction]:
        """Create ABA purchase form using structured PAYMENT_PURCHASE_FORM_REQUEST_SCHEMA."""
        return await self.create_purchase_for_sale(
            sale_id        = payload.sale_id
            , payment_option = payload.payment_option
            , created_by     = created_by
        )


    async def create_purchase_payload(
        self
        , payload    : PAYMENT_PURCHASE_FORM_REQUEST_SCHEMA
        , created_by : UUID
    ) -> Tuple[str, Dict[str, str], PaymentTransaction]:
        """Create ABA purchase form using structured PAYMENT_PURCHASE_FORM_REQUEST_SCHEMA."""
        return await self.create_purchase_for_sale(
            sale_id        = payload.sale_id
            , payment_option = payload.payment_option
            , created_by     = created_by
        )
