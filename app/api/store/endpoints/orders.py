"""Storefront customer order & checkout endpoints â€” /api/store/v1/orders"""
from __future__ import annotations

import secrets
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.store.auth import get_optional_customer, require_customer
from app.core.database import get_db
from app.core.security import hash_password
from app.models import Customer
from app.models import PaymentTransaction
from app.models import ProductVariant
from app.models import Sale, SaleItem
from app.models import User
from app.repositories.user_repository import UserRepository
from app.services.misc_service import PromotionService
from app.services.product_service import ProductService
from app.services.sale_service import SaleService
from app.utils.generators import generate_customer_code

router = APIRouter(prefix="/orders", tags=["Store Orders"])

ONLINE_ORDER_TAG = "[ONLINE STORE]"
GUEST_ACTOR_USERNAME = "online_store_guest"


class StoreOrderItemCreate(BaseModel):
    variant_id: UUID
    quantity: int = Field(ge=1)


class StoreOrderCreate(BaseModel):
    items: list[StoreOrderItemCreate] = Field(min_length=1)
    payment_method: str = "ABA_KHQR"
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    shipping_address: str | None = None
    notes: str | None = None
    coupon_code: str | None = None
    create_draft: bool = False


class StoreOrderCompleteRequest(BaseModel):
    payment_method: str = "ABA_KHQR"
    reference_number: str | None = None


class StoreCouponValidateRequest(BaseModel):
    code: str
    cart_total: Decimal = Field(ge=0)


def _serialize_order(sale: Sale) -> dict:
    items_out = []
    for item in sale.items or []:
        variant = getattr(item, "variant", None)
        product = getattr(variant, "product", None) if variant else None
        color = getattr(variant, "color", None) if variant else None
        size = getattr(variant, "size", None) if variant else None
        items_out.append(
            {
                "id": str(item.id),
                "variant_id": str(item.variant_id),
                "sku": getattr(variant, "sku", None),
                "product_name": getattr(product, "name", None) or getattr(variant, "sku", "Item"),
                "color": getattr(color, "name", None),
                "size": getattr(size, "name", None),
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "discount_amount": float(item.discount_amount or 0),
                "subtotal": float(item.subtotal),
            }
        )
    payments_out = [
        {
            "payment_method": p.payment_method,
            "amount": float(p.amount),
            "status": getattr(p, "status", "PAID"),
        }
        for p in (sale.payments or [])
    ]
    return {
        "id": str(sale.id),
        "invoice_number": sale.invoice_number,
        "subtotal": float(sale.subtotal),
        "discount_amount": float(sale.discount_amount or 0),
        "tax_amount": float(sale.tax_amount or 0),
        "total": float(sale.total),
        "payment_status": sale.payment_status,
        "sale_status": sale.sale_status,
        "notes": sale.notes,
        "created_at": sale.created_at.isoformat() if sale.created_at else None,
        "items": items_out,
        "payments": payments_out,
    }


def _order_Load_options():
    return [
        selectinload(Sale.items)
        .selectinload(SaleItem.variant)
        .options(
            selectinload(ProductVariant.product),
            selectinload(ProductVariant.color),
            selectinload(ProductVariant.size),
        ),
        selectinload(Sale.payments),
    ]


async def _get_guest_actor(db: AsyncSession) -> User:
    """Dedicated, non-loginable system user that owns guest (anonymous) online orders.

    Status is INACTIVE and the password is random, so it can never authenticate and
    never appears as an active staff member in cashier/audit reporting.
    """
    actor = (
        await db.execute(select(User).where(User.username == GUEST_ACTOR_USERNAME))
    ).scalar_one_or_none()
    if actor:
        return actor
    actor = User(
        username=GUEST_ACTOR_USERNAME,
        email=f"{GUEST_ACTOR_USERNAME}@system.invalid",
        full_name="Online Store (Guest)",
        hashed_password=hash_password(secrets.token_urlsafe(48)),
        status="INACTIVE",
    )
    db.add(actor)
    await db.flush()
    return actor


async def _load_online_order(
    db: AsyncSession,
    order_id: UUID,
    current_customer: User | None,
) -> Sale:
    """Load a storefront order the caller is allowed to touch, else raise 404.

    - Only storefront orders are reachable here (POS sales are never exposed).
    - Orders owned by a registered customer are visible only to that customer.
    - Guest orders are protected by their unguessable UUID (capability URL).
    """
    sale = (
        await db.execute(
            select(Sale).where(Sale.id == order_id).options(*_order_Load_options())
        )
    ).scalar_one_or_none()
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if not sale or not (sale.notes or "").startswith(ONLINE_ORDER_TAG):
        raise not_found

    owner = await UserRepository(db).get_by_id(sale.cashier_id)
    owner_is_customer = bool(owner and any(r.name == "CUSTOMER" for r in owner.roles))
    if owner_is_customer and (not current_customer or current_customer.id != owner.id):
        raise not_found
    return sale


async def _verify_and_settle_payment(db: AsyncSession, sale: Sale) -> None:
    """Re-check the latest PENDING ABA transaction of the order with ABA itself.

    `PaymentService.refresh_status` is the only code path allowed to mark an online
    order as paid: it asks ABA and completes the sale on APPROVED.
    """
    from app.services.payment_service import PaymentService

    tx_id = (
        await db.execute(
            select(PaymentTransaction.id)
            .where(
                PaymentTransaction.sale_id == sale.id,
                PaymentTransaction.status == "PENDING",
            )
            .order_by(PaymentTransaction.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if tx_id:
        await PaymentService(db).refresh_status(tx_id)
        await db.commit()


@router.post("/validate-coupon")
async def validate_store_coupon(
    body: StoreCouponValidateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Validate a promo/coupon code against the customer's bag subtotal."""
    promo_service = PromotionService(db)
    res = await promo_service.validate_coupon(body.code.strip(), cart_total=body.cart_total)
    return {
        "valid": res.valid,
        "code": body.code.strip().upper(),
        "discount_amount": float(res.discount_amount or 0),
        "message": res.message,
        "promotion_id": str(res.promotion_id) if res.promotion_id else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_store_order(
    payload: StoreOrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_customer: Annotated[User | None, Depends(get_optional_customer)] = None,
) -> dict:
    """Create a storefront order in DRAFT state.

    Orders are never marked paid here. Payment is confirmed server-side only, after the
    ABA gateway reports APPROVED (see ``PaymentService.refresh_status``); stock is
    deducted at that moment.
    """
    # 1. Resolve acting user ID for Sale.cashier_id
    if current_customer:
        actor_user_id: UUID = current_customer.id
    else:
        actor_user_id = (await _get_guest_actor(db)).id

    # 2. Resolve or create Customer record for order tracking & loyalty points
    email = (payload.customer_email or (current_customer.email if current_customer else "") or "").strip().lower() or None
    phone = (payload.customer_phone or "").strip() or None
    name = (payload.customer_name or (current_customer.full_name if current_customer else "") or "Online Customer").strip()

    customer_id: UUID | None = None
    if email or phone:
        filters = []
        if email:
            filters.append(Customer.email == email)
        if phone:
            filters.append(Customer.phone == phone)
        existing_cust = (
            await db.execute(select(Customer).where(or_(*filters)).limit(1))
        ).scalar_one_or_none()
        if existing_cust:
            customer_id = existing_cust.id
        elif phone:
            code = await generate_customer_code(db)
            new_cust = Customer(
                customer_code=code,
                name=name,
                phone=phone,
                email=email,
                address=payload.shipping_address,
            )
            db.add(new_cust)
            await db.flush()
            customer_id = new_cust.id

    # 3. Prepare items & calculate cart total for optional coupon validation
    sale_service = SaleService(db)
    items_data = []
    estimated_subtotal = Decimal("0")
    for item in payload.items:
        variant = await sale_service.variant_repo.get_by_id(item.variant_id)
        if not variant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product variant {item.variant_id} not found.",
            )
        estimated_subtotal += variant.selling_price * item.quantity
        items_data.append(
            {
                "variant_id": variant.id,
                "quantity": item.quantity,
                "unit_price": variant.selling_price,
                "discount_amount": Decimal("0"),
            }
        )

    discount_amount = Decimal("0")
    promotion_id: UUID | None = None
    if payload.coupon_code:
        promo_service = PromotionService(db)
        coupon_res = await promo_service.validate_coupon(
            payload.coupon_code.strip(), cart_total=estimated_subtotal
        )
        if not coupon_res.valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=coupon_res.message)
        discount_amount = coupon_res.discount_amount
        promotion_id = coupon_res.promotion_id

    note_parts = [ONLINE_ORDER_TAG]
    if payload.shipping_address:
        note_parts.append(f"Ship to: {payload.shipping_address}")
    if payload.notes:
        note_parts.append(payload.notes)

    sale = await sale_service.create_sale(
        branch_id=None,
        warehouse_id=None,
        cashier_id=actor_user_id,
        items_data=items_data,
        customer_id=customer_id,
        discount_amount=discount_amount,
        tax_amount=Decimal("0"),
        notes=" | ".join(note_parts),
        promotion_id=promotion_id,
    )

    await db.commit()

    final_sale = (
        await db.execute(
            select(Sale).where(Sale.id == sale.id).options(*_order_Load_options())
        )
    ).scalar_one()
    return _serialize_order(final_sale)


@router.post("/{order_id}/khqr", status_code=status.HTTP_201_CREATED)
async def create_store_order_khqr(
    order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_customer: Annotated[User | None, Depends(get_optional_customer)] = None,
) -> dict:
    """Generate an ABA PayWay KHQR payload & QR image for a storefront order.

    Failures from the gateway are surfaced as errors (HTTP 502); a QR that cannot be
    paid is never fabricated.
    """
    import base64

    from app.services.payment_service import PaymentService
    from app.utils.qr import generate_qr_png

    sale = await _load_online_order(db, order_id, current_customer)

    tx = await PaymentService(db).create_khqr_for_sale(
        sale_id=sale.id,
        created_by=sale.cashier_id,
    )
    tx.channel = "ONLINE"
    await db.commit()

    qr_img = getattr(tx, "qr_image", None)
    if not qr_img and tx.qr_string:
        png_bytes = generate_qr_png(tx.qr_string)
        qr_img = f"data:image/png;base64,{base64.b64encode(png_bytes).decode('ascii')}"
    return {
        "payment_id": str(tx.id),
        "tran_id": tx.tran_id,
        "order_id": str(sale.id),
        "status": tx.status,
        "amount": float(tx.amount),
        "currency": tx.currency,
        "qr_string": tx.qr_string,
        "qr_image": qr_img,
        "expires_at": tx.expires_at.isoformat() if tx.expires_at else None,
    }


@router.get("/{order_id}/payment-status")
async def get_store_order_payment_status(
    order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_customer: Annotated[User | None, Depends(get_optional_customer)] = None,
    payment_id: UUID | None = None,  # kept for client compatibility; ignored
) -> dict:
    """Poll payment status for a storefront order (verified with ABA, never client-claimed)."""
    sale = await _load_online_order(db, order_id, current_customer)
    await _verify_and_settle_payment(db, sale)

    # Re-read: settlement may have completed the sale in this request.
    sale = await _load_online_order(db, order_id, current_customer)
    tx_status = (
        await db.execute(
            select(PaymentTransaction.status)
            .where(PaymentTransaction.sale_id == sale.id)
            .order_by(PaymentTransaction.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return {
        "order_id": str(sale.id),
        "invoice_number": sale.invoice_number,
        "sale_status": sale.sale_status,
        "payment_status": sale.payment_status,
        "transaction_status": tx_status or ("APPROVED" if sale.payment_status == "PAID" else "PENDING"),
    }


@router.post("/{order_id}/complete")
async def complete_store_order(
    order_id: UUID,
    body: StoreOrderCompleteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_customer: Annotated[User | None, Depends(get_optional_customer)] = None,
) -> dict:
    """Return the finalised order once ABA has confirmed payment.

    This endpoint can no longer mark an order paid on the client's word: the request body
    (``payment_method`` / ``reference_number``) is ignored. If the gateway has not
    approved the payment the order stays DRAFT and HTTP 402 is returned.
    """
    sale = await _load_online_order(db, order_id, current_customer)

    if sale.sale_status == "DRAFT":
        await _verify_and_settle_payment(db, sale)
        sale = await _load_online_order(db, order_id, current_customer)
        if sale.sale_status == "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Payment has not been confirmed by the payment gateway.",
            )

    return _serialize_order(sale)


@router.get("")
@router.get("/", include_in_schema=False)
async def list_my_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_customer: Annotated[User, Depends(require_customer)],
) -> list[dict]:
    """List orders placed by the authenticated customer."""
    cust_ids: list[UUID] = []
    if current_customer.email:
        res = await db.execute(
            select(Customer.id).where(Customer.email == current_customer.email.lower())
        )
        cust_ids = list(res.scalars().all())

    conds = [Sale.cashier_id == current_customer.id]
    if cust_ids:
        conds.append(Sale.customer_id.in_(cust_ids))

    stmt = (
        select(Sale)
        .where(or_(*conds))
        .options(*_order_Load_options())
        .order_by(Sale.created_at.desc())
        .limit(50)
    )
    sales = (await db.execute(stmt)).scalars().all()
    return [_serialize_order(s) for s in sales]


@router.get("/{order_id}")
async def get_store_order(
    order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_customer: Annotated[User | None, Depends(get_optional_customer)] = None,
) -> dict:
    """Get a storefront order summary/receipt by ID (owner only for customer orders)."""
    sale = await _load_online_order(db, order_id, current_customer)
    return _serialize_order(sale)
