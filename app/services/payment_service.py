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
from uuid import UUID

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import PaymentTransaction
from app.models import Sale
from app.services.payway import map_payway_status, payway_client
from app.services.sale_service import SaleService


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
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=4,
        )
        qr.add_data(qr_string)
        qr.make(fit=True)
        img: PilImage = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception as exc:
        logger.warning(f"[PaymentService] QR image build failed: {exc}")
        return ""


# ── Service ──────────────────────────────────────────────────────────────────

class PaymentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _callback_urls(self, tran_id: str) -> tuple[str, str, str]:
        """Return (return_url, cancel_url, continue_success_url)."""
        base = (settings.PAYWAY_CALLBACK_BASE_URL or "https://example.com").rstrip("/")
        return (
            f"{base}/api/payments/aba/pushback",
            f"{base}/api/payments/aba/pushback",
            f"{base}/api/payments/aba/pushback",
        )

    async def create_khqr_for_sale(
        self,
        sale_id: UUID,
        created_by: UUID,
    ) -> PaymentTransaction:
        """Create ABA KHQR for a DRAFT sale.

        1. Load the sale.
        2. Check no PENDING tx already exists.
        3. Call PayWay Purchase.
        4. Persist PaymentTransaction.
        5. Return it (qr_image is a data URL).
        """
        sale: Sale | None = await self.db.get(Sale, sale_id)
        if not sale:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
        if sale.sale_status != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Sale is already {sale.sale_status}",
            )

        # Invalidate any stale PENDING tx for this sale. Re-check each one first so a
        # QR that was just paid is never discarded, then close the rest at ABA so the
        # old QR can no longer be paid after a new one is issued.
        existing_result = await self.db.execute(
            select(PaymentTransaction.id).where(
                PaymentTransaction.sale_id == sale_id,
                PaymentTransaction.status == "PENDING",
            )
        )
        for stale_id in existing_result.scalars().all():
            stale = await self.refresh_status(stale_id)
            if stale.status == "APPROVED":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The previous QR was already paid",
                )
            if stale.status == "PENDING":
                try:
                    await payway_client.close_transaction(stale.tran_id)
                except Exception as exc:
                    logger.warning(f"[PaymentService] Close stale tx error (continuing): {exc}")
                stale.status = "CANCELLED"
                logger.info(f"[PaymentService] Cancelled stale tx {stale.tran_id}")

        tran_id = _generate_tran_id()
        amount = float(sale.total)
        return_url, cancel_url, success_url = self._callback_urls(tran_id)

        try:
            aba_resp = await payway_client.create_khqr(
                tran_id=tran_id,
                amount_usd=amount,
                item_name=f"Sale {sale.invoice_number or 'Order'}",
            )
        except Exception as exc:
            logger.error(f"[PaymentService] PayWay generate-qr error: {exc}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"ABA PayWay error: {exc}",
            ) from exc

        qr_string = aba_resp.get("qrString") or aba_resp.get("qr_string") or ""
        qr_image_url = aba_resp.get("qrImage") or aba_resp.get("qr_image") or ""
        deeplink = aba_resp.get("abapay_deeplink") or ""

        # Strip sensitive fields before storage
        safe_resp = {k: v for k, v in aba_resp.items() if k not in ("hash",)}

        tx = PaymentTransaction(
            provider="ABA_PAYWAY",
            tran_id=tran_id,
            sale_id=sale_id,
            channel="POS",
            payment_option="abapay_khqr",
            amount=amount,
            currency="USD",
            status="PENDING",
            qr_string=qr_string,
            checkout_url=deeplink,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.PAYWAY_QR_LIFETIME_MINUTES),
            last_response=safe_resp,
            created_by=created_by,
        )
        self.db.add(tx)
        await self.db.flush()
        await self.db.refresh(tx)

        # Render a crisp, square 1:1 QR PNG directly from the official PayWay qr_string
        # payload (with built-in 4-module quiet zone) so the POS payment card displays a
        # full-size 240-280px QR without nesting PayWay's 216x448 poster card inside it.
        tx.qr_image = _qr_to_data_url(qr_string) or qr_image_url  # type: ignore[attr-defined]
        logger.info(f"[PaymentService] KHQR created tran_id={tran_id} sale={sale_id}")
        return tx

    async def create_purchase_for_sale(
        self,
        sale_id: UUID,
        payment_option: str,
        created_by: UUID,
    ) -> tuple[str, dict[str, str], PaymentTransaction]:
        """Create an ABA PayWay purchase transaction for checkout modal / bottom sheet.

        Returns:
            (action_url, form_data, PaymentTransaction)
        """
        sale: Sale | None = await self.db.get(Sale, sale_id)
        if not sale:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
        if sale.sale_status != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Sale is already {sale.sale_status}",
            )

        # Invalidate any stale PENDING tx for this sale
        existing_result = await self.db.execute(
            select(PaymentTransaction.id).where(
                PaymentTransaction.sale_id == sale_id,
                PaymentTransaction.status == "PENDING",
            )
        )
        for stale_id in existing_result.scalars().all():
            stale = await self.refresh_status(stale_id)
            if stale.status == "APPROVED":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The previous payment was already completed",
                )
            if stale.status == "PENDING":
                try:
                    await payway_client.close_transaction(stale.tran_id)
                except Exception as exc:
                    logger.warning(f"[PaymentService] Close stale tx error (continuing): {exc}")
                stale.status = "CANCELLED"
                logger.info(f"[PaymentService] Cancelled stale tx {stale.tran_id}")

        tran_id = _generate_tran_id()
        amount = float(sale.total)

        action_url, form_data = payway_client.build_purchase_form_data(
            tran_id=tran_id,
            amount_usd=amount,
            payment_option=payment_option or "",
            item_name=f"Sale {sale.invoice_number or 'Order'}",
        )

        safe_form = {k: v for k, v in form_data.items() if k not in ("hash",)}

        tx = PaymentTransaction(
            provider="ABA_PAYWAY",
            tran_id=tran_id,
            sale_id=sale_id,
            channel="POS_MODAL",
            payment_option=payment_option or "all",
            amount=amount,
            currency="USD",
            status="PENDING",
            qr_string=None,
            checkout_url=action_url,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.PAYWAY_QR_LIFETIME_MINUTES),
            last_response={"form_data": safe_form},
            created_by=created_by,
        )
        self.db.add(tx)
        await self.db.flush()
        await self.db.refresh(tx)

        logger.info(
            f"[PaymentService] Purchase form created tran_id={tran_id} sale={sale_id} option={payment_option}"
        )
        return action_url, form_data, tx

    async def refresh_status(self, tx_id: UUID) -> PaymentTransaction:
        """Check ABA for the latest status. On APPROVED, complete the sale.

        Uses SELECT FOR UPDATE to prevent concurrent double-completion.
        """
        result = await self.db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.id == tx_id)
            .with_for_update()
        )
        tx: PaymentTransaction | None = result.scalar_one_or_none()
        if not tx:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

        if tx.status not in ("PENDING",):
            return tx   # Already resolved, no need to re-check

        try:
            aba_resp = await payway_client.check_transaction(tx.tran_id)
        except Exception as exc:
            logger.warning(f"[PaymentService] Check transaction error: {exc}")
            return tx

        safe_resp = {k: v for k, v in aba_resp.items() if k not in ("hash",)}
        tx.last_response = safe_resp

        new_status, apv = map_payway_status(aba_resp)
        tx.status = new_status
        if apv:
            tx.apv = apv

        if new_status == "APPROVED":
            tx.paid_at = datetime.now(timezone.utc)

            # Determine payment method & enrich transaction details (e.g. Card vs KHQR)
            payment_method_name = "CARD" if tx.payment_option == "cards" else "ABA_KHQR"
            card_info = ""
            try:
                detail_resp = await payway_client.get_transaction_detail(tx.tran_id)
                detail_data = detail_resp.get("data") or {}
                pay_type = (detail_data.get("payment_type") or "").upper()
                payer_acc = detail_data.get("payer_account") or ""
                if pay_type in ("VISA", "MC", "JCB", "CUP") or tx.payment_option == "cards":
                    payment_method_name = "CARD"
                    card_info = f"{pay_type} {payer_acc}".strip()
                elif pay_type in ("ABA PAY", "KHQR"):
                    payment_method_name = "ABA_KHQR"

                safe_detail = {k: v for k, v in detail_data.items() if k not in ("hash",)}
                if isinstance(tx.last_response, dict):
                    tx.last_response = {**tx.last_response, "detail": safe_detail}
            except Exception as detail_exc:
                logger.warning(f"[PaymentService] Could not fetch detail: {detail_exc}")

            # Complete the sale (idempotent due to FOR UPDATE + status guard)
            if tx.sale_id:
                sale_result = await self.db.execute(
                    select(Sale).where(Sale.id == tx.sale_id).with_for_update()
                )
                sale: Sale | None = sale_result.scalar_one_or_none()
                if sale and sale.sale_status == "DRAFT":
                    svc = SaleService(self.db)
                    ref_text = tx.apv or tx.tran_id
                    if card_info:
                        ref_text = f"{ref_text} ({card_info})"

                    await svc.complete_sale(
                        sale,
                        payments=[
                            {
                                "payment_method": payment_method_name,
                                "amount": float(tx.amount),
                                "reference_number": ref_text,
                            }
                        ],
                    )
                    logger.info(
                        f"[PaymentService] Sale {sale.id} completed via {payment_method_name} tran_id={tx.tran_id}"
                    )

                    # Post-completion bookkeeping that every gateway-settled sale needs
                    # (pushback, reconciler, POS poll and storefront poll all land here).
                    try:
                        from app.services.product_service import ProductService

                        await ProductService.increment_inventory_version(self.db)
                        if sale.promotion_id and (sale.notes or "").startswith("[ONLINE STORE]"):
                            from app.services.misc_service import PromotionService

                            await PromotionService(self.db).record_usage(sale.promotion_id)
                    except Exception as post_exc:
                        logger.warning(f"[PaymentService] Post-completion bookkeeping failed: {post_exc}")

                    # Fire Telegram notification (non-blocking)
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
                        logger.warning(f"[PaymentService] Telegram notify failed: {tg_exc}")

        elif new_status in ("DECLINED", "CANCELLED"):
            logger.info(f"[PaymentService] tran_id={tx.tran_id} is {new_status}")

        await self.db.flush()
        return tx

    async def cancel(self, tx_id: UUID) -> PaymentTransaction:
        """Cancel a PENDING QR — call Close Transaction then mark CANCELLED."""
        result = await self.db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.id == tx_id)
            .with_for_update()
        )
        tx: PaymentTransaction | None = result.scalar_one_or_none()
        if not tx:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

        if tx.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot cancel a transaction in status {tx.status}",
            )

        # Guard against a payment that landed a moment before the cashier pressed
        # cancel: re-check with ABA first. If it was paid, refresh_status completes
        # the sale and we must NOT close/cancel the transaction.
        tx = await self.refresh_status(tx_id)
        if tx.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Payment is already {tx.status}; cannot cancel",
            )

        try:
            await payway_client.close_transaction(tx.tran_id)
        except Exception as exc:
            logger.warning(f"[PaymentService] Close transaction error (continuing): {exc}")

        tx.status = "CANCELLED"
        await self.db.flush()
        return tx
