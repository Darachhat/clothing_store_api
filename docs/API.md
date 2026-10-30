# Clothing Store API Reference

Total operations: **378**.
Generated from the FastAPI OpenAPI spec (`app.openapi()`). Interactive docs: `/docs`.

## Surfaces

| Prefix | Audience |
| --- | --- |
| `/api/admin/v1` | Admin dashboard (canonical admin surface) |
| `/api/v1` | Legacy alias of the admin surface (kept for backward compatibility) |
| `/api/cashier/v1` | Cashier POS |
| `/api/store/v1` | Customer storefront |

`/api/v1/store/*` redirects to `/api/store/v1/*` and `/api/v1/pos/*` to `/api/cashier/v1/*`.

## Conventions

- Auth: `Authorization: Bearer <JWT>`; endpoints marked 🔒 require it (role/permission enforced server-side).
- Updates accept both `PUT` and `PATCH` on the same path.
- Errors: JSON `{ "detail": ... }` with 400/401/403/404/409/422 status codes.
- Aliases kept for compatibility: `POST /sales/{id}/void` = `/cancel`; `POST /inventory/adjust` = `/adjustments`; `POST /promotions/validate-coupon` = `/validate`; `POST /labels/download` = label generation; `GET /roles/permissions` = `/roles/permissions/all`.
- Stock adjustment body accepts `quantity_delta` or absolute `new_quantity`.
- Reports accept `start_date`/`end_date` or `from_date`/`to_date` (default last 30 days) and `group_by` (`day|week|month`); dashboard `period`: `today|yesterday|7days|last_7_days|30days|last_30_days|this_month`.

## `api/admin/v1`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/admin/v1/attachments` | List stored attachments | 🔒 |  | AttachmentListResponse |
| POST | `/api/admin/v1/attachments/upload` | Upload a single attachment | 🔒 |  | AttachmentResponse |
| POST | `/api/admin/v1/attachments/upload-multiple` | Upload multiple attachments | 🔒 |  | AttachmentResponse[] |
| GET | `/api/admin/v1/attachments/{object_name}` | Get direct link to attachment | 🔒 |  |  |
| DELETE | `/api/admin/v1/attachments/{object_name}` | Delete an attachment | 🔒 |  |  |
| POST | `/api/admin/v1/auth/change-password` | Change Password | 🔒 | ChangePasswordRequest | object |
| GET | `/api/admin/v1/auth/clients` | List System Clients |  |  | RESPONSE_ENVELOPE_List_SYSTEM_CLIENT_RESPONSE_SCHEMA__ |
| POST | `/api/admin/v1/auth/clients` | Register System Client |  | SYSTEM_CLIENT_CREATE_SCHEMA | RESPONSE_ENVELOPE_API_KEY_CREATED_SCHEMA_ |
| PUT | `/api/admin/v1/auth/clients/{code}/revoke` | Revoke System Client |  |  | RESPONSE_ENVELOPE_SYSTEM_CLIENT_RESPONSE_SCHEMA_ |
| POST | `/api/admin/v1/auth/login` | Login |  | LoginRequest | LoginResponse |
| POST | `/api/admin/v1/auth/logout` | Logout |  | LogoutRequest | object |
| GET | `/api/admin/v1/auth/me` | Get Me | 🔒 |  | UserOut |
| POST | `/api/admin/v1/auth/refresh` | Refresh |  | RefreshRequest | TokenResponse |
| GET | `/api/admin/v1/branches/` | List Branches | 🔒 |  | BranchOut[] |
| GET | `/api/admin/v1/brands/` | List Brands | 🔒 |  | BrandOut[] |
| POST | `/api/admin/v1/brands/` | Create Brand | 🔒 | BrandCreate | BrandOut |
| GET | `/api/admin/v1/brands/{id}` | Get Brand | 🔒 |  | BrandOut |
| PATCH | `/api/admin/v1/brands/{id}` | Update Brand | 🔒 | BrandUpdate | BrandOut |
| PUT | `/api/admin/v1/brands/{id}` | Update Brand | 🔒 | BrandUpdate | BrandOut |
| DELETE | `/api/admin/v1/brands/{id}` | Delete Brand | 🔒 |  |  |
| GET | `/api/admin/v1/categories/` | List Categories | 🔒 |  | CategoryOut[] |
| POST | `/api/admin/v1/categories/` | Create Category | 🔒 | CategoryCreate | CategoryOut |
| GET | `/api/admin/v1/categories/{id}` | Get Category | 🔒 |  | CategoryOut |
| PATCH | `/api/admin/v1/categories/{id}` | Update Category | 🔒 | CategoryUpdate | CategoryOut |
| PUT | `/api/admin/v1/categories/{id}` | Update Category | 🔒 | CategoryUpdate | CategoryOut |
| DELETE | `/api/admin/v1/categories/{id}` | Delete Category | 🔒 |  |  |
| GET | `/api/admin/v1/colors/` | List Colors | 🔒 |  | ColorOut[] |
| POST | `/api/admin/v1/colors/` | Create Color | 🔒 | ColorCreate | ColorOut |
| GET | `/api/admin/v1/colors/{id}` | Get Color | 🔒 |  | ColorOut |
| PATCH | `/api/admin/v1/colors/{id}` | Update Color | 🔒 | ColorUpdate | ColorOut |
| PUT | `/api/admin/v1/colors/{id}` | Update Color | 🔒 | ColorUpdate | ColorOut |
| DELETE | `/api/admin/v1/colors/{id}` | Delete Color | 🔒 |  |  |
| GET | `/api/admin/v1/customers/` | List Customers | 🔒 |  | CustomerListResponse |
| POST | `/api/admin/v1/customers/` | Create Customer | 🔒 | CustomerCreate | CustomerResponse |
| GET | `/api/admin/v1/customers/{customer_id}` | Get Customer | 🔒 |  | CustomerResponse |
| PATCH | `/api/admin/v1/customers/{customer_id}` | Update Customer | 🔒 | CustomerUpdate | CustomerResponse |
| PUT | `/api/admin/v1/customers/{customer_id}` | Update Customer | 🔒 | CustomerUpdate | CustomerResponse |
| POST | `/api/admin/v1/customers/{customer_id}/points` | Adjust Loyalty Points | 🔒 | AdjustPointsRequest | LoyaltyAccountSchema |
| GET | `/api/admin/v1/expenses` | List Expenses | 🔒 |  | ExpenseOut[] |
| POST | `/api/admin/v1/expenses` | Create Expense | 🔒 | ExpenseCreate | ExpenseOut |
| GET | `/api/admin/v1/expenses/categories` | List Categories | 🔒 |  | ExpenseCategoryOut[] |
| POST | `/api/admin/v1/expenses/categories` | Create Category | 🔒 | ExpenseCategoryCreate | ExpenseCategoryOut |
| PUT | `/api/admin/v1/expenses/categories/{cat_id}` | Update Category | 🔒 | ExpenseCategoryUpdate | ExpenseCategoryOut |
| PATCH | `/api/admin/v1/expenses/categories/{cat_id}` | Update Category | 🔒 | ExpenseCategoryUpdate | ExpenseCategoryOut |
| GET | `/api/admin/v1/expenses/{expense_id}` | Get Expense | 🔒 |  | ExpenseOut |
| PUT | `/api/admin/v1/expenses/{expense_id}` | Update Expense | 🔒 | ExpenseUpdate | ExpenseOut |
| PATCH | `/api/admin/v1/expenses/{expense_id}` | Update Expense | 🔒 | ExpenseUpdate | ExpenseOut |
| POST | `/api/admin/v1/expenses/{expense_id}/approve` | Approve Expense | 🔒 |  | ExpenseOut |
| POST | `/api/admin/v1/expenses/{expense_id}/reject` | Reject Expense | 🔒 |  | ExpenseOut |
| POST | `/api/admin/v1/inventory/adjustments` | Create Adjustment | 🔒 | StockAdjustmentCreate | InventoryStockOut |
| GET | `/api/admin/v1/inventory/movements` | List Movements | 🔒 |  | InventoryMovementOut[] |
| GET | `/api/admin/v1/inventory/stocks` | List Stocks | 🔒 |  | InventoryStockOut[] |
| GET | `/api/admin/v1/inventory/transfers/` | List Transfers | 🔒 |  | StockTransferOut[] |
| POST | `/api/admin/v1/inventory/transfers/` | Create Transfer | 🔒 | StockTransferCreate | StockTransferOut |
| POST | `/api/admin/v1/inventory/transfers/{id}/approve` | Approve Transfer | 🔒 |  | StockTransferOut |
| POST | `/api/admin/v1/inventory/transfers/{id}/cancel` | Cancel Transfer | 🔒 |  | StockTransferOut |
| POST | `/api/admin/v1/inventory/transfers/{id}/dispatch` | Dispatch Transfer | 🔒 |  | StockTransferOut |
| POST | `/api/admin/v1/inventory/transfers/{id}/receive` | Receive Transfer | 🔒 |  | StockTransferOut |
| POST | `/api/admin/v1/labels/generate` | Generate Labels | 🔒 | LabelGenerateRequest |  |
| GET | `/api/admin/v1/product-variants/` | List Variants | 🔒 |  | ProductVariantOut[] |
| POST | `/api/admin/v1/product-variants/` | Create Variant | 🔒 | ProductVariantCreate | ProductVariantOut |
| GET | `/api/admin/v1/product-variants/by-barcode/{barcode}` | Get Variant By Barcode | 🔒 |  | ProductVariantOut |
| GET | `/api/admin/v1/product-variants/by-qr/{reference}` | Get Variant By Qr | 🔒 |  | ProductVariantOut |
| GET | `/api/admin/v1/product-variants/by-sku/{sku}` | Get Variant By Sku | 🔒 |  | ProductVariantOut |
| DELETE | `/api/admin/v1/product-variants/{id}` | Delete Variant | 🔒 |  |  |
| GET | `/api/admin/v1/product-variants/{id}` | Get Variant | 🔒 |  | ProductVariantOut |
| PATCH | `/api/admin/v1/product-variants/{id}` | Update Variant | 🔒 | ProductVariantUpdate | ProductVariantOut |
| PUT | `/api/admin/v1/product-variants/{id}` | Update Variant | 🔒 | ProductVariantUpdate | ProductVariantOut |
| GET | `/api/admin/v1/product-variants/{id}/barcode` | Get Variant Barcode | 🔒 |  |  |
| GET | `/api/admin/v1/product-variants/{id}/qr` | Get Variant Qr | 🔒 |  |  |
| GET | `/api/admin/v1/products/` | List Products | 🔒 |  | ProductPaginationResponse | ProductPaginationWithVariantsResponse |
| POST | `/api/admin/v1/products/` | Create Product | 🔒 | ProductCreate | ProductOut |
| GET | `/api/admin/v1/products/{id}` | Get Product | 🔒 |  | ProductWithVariants |
| PATCH | `/api/admin/v1/products/{id}` | Update Product | 🔒 | ProductUpdate | ProductOut |
| PUT | `/api/admin/v1/products/{id}` | Update Product | 🔒 | ProductUpdate | ProductOut |
| DELETE | `/api/admin/v1/products/{id}` | Delete Product | 🔒 |  |  |
| GET | `/api/admin/v1/products/{id}/variants` | Get Product Variants | 🔒 |  | ProductVariantOut[] |
| GET | `/api/admin/v1/promotions` | List Promotions | 🔒 |  | PromotionOut[] |
| POST | `/api/admin/v1/promotions` | Create Promotion | 🔒 | PromotionCreate | PromotionOut |
| POST | `/api/admin/v1/promotions/validate` | Validate Coupon | 🔒 | CouponValidationRequest | CouponValidationResponse |
| GET | `/api/admin/v1/promotions/{promo_id}` | Get Promotion | 🔒 |  | PromotionOut |
| PUT | `/api/admin/v1/promotions/{promo_id}` | Update Promotion | 🔒 | PromotionUpdate | PromotionOut |
| PATCH | `/api/admin/v1/promotions/{promo_id}` | Update Promotion | 🔒 | PromotionUpdate | PromotionOut |
| DELETE | `/api/admin/v1/promotions/{promo_id}` | Delete Promotion | 🔒 |  |  |
| GET | `/api/admin/v1/purchases` | List Purchase Orders | 🔒 |  | PurchaseOrderOut[] |
| POST | `/api/admin/v1/purchases` | Create Purchase Order | 🔒 | PurchaseOrderCreate | PurchaseOrderOut |
| POST | `/api/admin/v1/purchases/receipts` | Create Goods Receipt | 🔒 | GoodsReceiptCreate | GoodsReceiptOut |
| GET | `/api/admin/v1/purchases/receipts/{receipt_id}` | Get Goods Receipt | 🔒 |  | GoodsReceiptOut |
| GET | `/api/admin/v1/purchases/{order_id}` | Get Purchase Order | 🔒 |  | PurchaseOrderOut |
| PATCH | `/api/admin/v1/purchases/{order_id}` | Update Purchase Order | 🔒 | PurchaseOrderUpdate | PurchaseOrderOut |
| POST | `/api/admin/v1/purchases/{order_id}/approve` | Approve Purchase Order | 🔒 |  | PurchaseOrderOut |
| POST | `/api/admin/v1/purchases/{order_id}/cancel` | Cancel Purchase Order | 🔒 |  | PurchaseOrderOut |
| GET | `/api/admin/v1/purchases/{order_id}/receipts` | List Order Receipts | 🔒 |  | GoodsReceiptOut[] |
| GET | `/api/admin/v1/reports/dashboard` | Dashboard | 🔒 |  | object |
| GET | `/api/admin/v1/reports/inventory` | Inventory Report | 🔒 |  | object |
| GET | `/api/admin/v1/reports/profit` | Profit Report | 🔒 |  | object |
| GET | `/api/admin/v1/reports/purchases` | Purchases Report | 🔒 |  | object |
| GET | `/api/admin/v1/reports/sales` | Sales Report | 🔒 |  | object |
| GET | `/api/admin/v1/returns/` | List Returns | 🔒 |  | ReturnOut[] |
| POST | `/api/admin/v1/returns/` | Create Return | 🔒 | ReturnCreate | ReturnOut |
| GET | `/api/admin/v1/roles` | List Roles | 🔒 |  | RoleOut[] |
| POST | `/api/admin/v1/roles` | Create Role | 🔒 | RoleCreate | RoleOut |
| GET | `/api/admin/v1/roles/permissions` | List Permissions | 🔒 |  | PermissionOut[] |
| PUT | `/api/admin/v1/roles/{role_id}` | Update Role | 🔒 | RoleUpdate | RoleOut |
| PATCH | `/api/admin/v1/roles/{role_id}` | Update Role | 🔒 | RoleUpdate | RoleOut |
| GET | `/api/admin/v1/sales/` | List Sales | 🔒 |  | SaleOut[] |
| POST | `/api/admin/v1/sales/` | Create Sale | 🔒 | SaleCreate | SaleOut |
| GET | `/api/admin/v1/sales/{id}` | Get Sale | 🔒 |  | SaleOut |
| POST | `/api/admin/v1/sales/{id}/cancel` | Cancel Sale | 🔒 |  | SaleOut |
| POST | `/api/admin/v1/sales/{id}/complete` | Complete Sale | 🔒 | SaleComplete | SaleOut |
| GET | `/api/admin/v1/sizes/` | List Sizes | 🔒 |  | SizeOut[] |
| POST | `/api/admin/v1/sizes/` | Create Size | 🔒 | SizeCreate | SizeOut |
| GET | `/api/admin/v1/sizes/{id}` | Get Size | 🔒 |  | SizeOut |
| PATCH | `/api/admin/v1/sizes/{id}` | Update Size | 🔒 | SizeUpdate | SizeOut |
| PUT | `/api/admin/v1/sizes/{id}` | Update Size | 🔒 | SizeUpdate | SizeOut |
| DELETE | `/api/admin/v1/sizes/{id}` | Delete Size | 🔒 |  |  |
| GET | `/api/admin/v1/suppliers/` | List Suppliers | 🔒 |  | SupplierOut[] |
| POST | `/api/admin/v1/suppliers/` | Create Supplier | 🔒 | SupplierCreate | SupplierOut |
| GET | `/api/admin/v1/suppliers/{id}` | Get Supplier | 🔒 |  | SupplierOut |
| PATCH | `/api/admin/v1/suppliers/{id}` | Update Supplier | 🔒 | SupplierUpdate | SupplierOut |
| PUT | `/api/admin/v1/suppliers/{id}` | Update Supplier | 🔒 | SupplierUpdate | SupplierOut |
| DELETE | `/api/admin/v1/suppliers/{id}` | Delete Supplier | 🔒 |  |  |
| GET | `/api/admin/v1/users` | List Users | 🔒 |  | UserOut[] |
| POST | `/api/admin/v1/users` | Create User | 🔒 | UserCreate | UserOut |
| GET | `/api/admin/v1/users/{user_id}` | Get User | 🔒 |  | UserOut |
| PUT | `/api/admin/v1/users/{user_id}` | Update User | 🔒 | UserUpdate | UserOut |
| PATCH | `/api/admin/v1/users/{user_id}` | Update User | 🔒 | UserUpdate | UserOut |
| DELETE | `/api/admin/v1/users/{user_id}` | Deactivate User | 🔒 |  | UserOut |

## `api/cashier/v1`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| POST | `/api/cashier/v1/auth/change-password` | Change Password | 🔒 | ChangePasswordRequest | object |
| GET | `/api/cashier/v1/auth/clients` | List System Clients |  |  | RESPONSE_ENVELOPE_List_SYSTEM_CLIENT_RESPONSE_SCHEMA__ |
| POST | `/api/cashier/v1/auth/clients` | Register System Client |  | SYSTEM_CLIENT_CREATE_SCHEMA | RESPONSE_ENVELOPE_API_KEY_CREATED_SCHEMA_ |
| PUT | `/api/cashier/v1/auth/clients/{code}/revoke` | Revoke System Client |  |  | RESPONSE_ENVELOPE_SYSTEM_CLIENT_RESPONSE_SCHEMA_ |
| POST | `/api/cashier/v1/auth/login` | Login |  | LoginRequest | LoginResponse |
| POST | `/api/cashier/v1/auth/logout` | Logout |  | LogoutRequest | object |
| GET | `/api/cashier/v1/auth/me` | Get Me | 🔒 |  | UserOut |
| POST | `/api/cashier/v1/auth/refresh` | Refresh |  | RefreshRequest | TokenResponse |
| GET | `/api/cashier/v1/branches/` | List Branches | 🔒 |  | BranchOut[] |
| GET | `/api/cashier/v1/brands/` | List Brands | 🔒 |  | BrandOut[] |
| POST | `/api/cashier/v1/brands/` | Create Brand | 🔒 | BrandCreate | BrandOut |
| GET | `/api/cashier/v1/brands/{id}` | Get Brand | 🔒 |  | BrandOut |
| PATCH | `/api/cashier/v1/brands/{id}` | Update Brand | 🔒 | BrandUpdate | BrandOut |
| PUT | `/api/cashier/v1/brands/{id}` | Update Brand | 🔒 | BrandUpdate | BrandOut |
| DELETE | `/api/cashier/v1/brands/{id}` | Delete Brand | 🔒 |  |  |
| GET | `/api/cashier/v1/categories/` | List Categories | 🔒 |  | CategoryOut[] |
| POST | `/api/cashier/v1/categories/` | Create Category | 🔒 | CategoryCreate | CategoryOut |
| GET | `/api/cashier/v1/categories/{id}` | Get Category | 🔒 |  | CategoryOut |
| PATCH | `/api/cashier/v1/categories/{id}` | Update Category | 🔒 | CategoryUpdate | CategoryOut |
| PUT | `/api/cashier/v1/categories/{id}` | Update Category | 🔒 | CategoryUpdate | CategoryOut |
| DELETE | `/api/cashier/v1/categories/{id}` | Delete Category | 🔒 |  |  |
| GET | `/api/cashier/v1/colors/` | List Colors | 🔒 |  | ColorOut[] |
| POST | `/api/cashier/v1/colors/` | Create Color | 🔒 | ColorCreate | ColorOut |
| GET | `/api/cashier/v1/colors/{id}` | Get Color | 🔒 |  | ColorOut |
| PATCH | `/api/cashier/v1/colors/{id}` | Update Color | 🔒 | ColorUpdate | ColorOut |
| PUT | `/api/cashier/v1/colors/{id}` | Update Color | 🔒 | ColorUpdate | ColorOut |
| DELETE | `/api/cashier/v1/colors/{id}` | Delete Color | 🔒 |  |  |
| GET | `/api/cashier/v1/customers/` | List Customers | 🔒 |  | CustomerListResponse |
| POST | `/api/cashier/v1/customers/` | Create Customer | 🔒 | CustomerCreate | CustomerResponse |
| GET | `/api/cashier/v1/customers/{customer_id}` | Get Customer | 🔒 |  | CustomerResponse |
| PATCH | `/api/cashier/v1/customers/{customer_id}` | Update Customer | 🔒 | CustomerUpdate | CustomerResponse |
| PUT | `/api/cashier/v1/customers/{customer_id}` | Update Customer | 🔒 | CustomerUpdate | CustomerResponse |
| POST | `/api/cashier/v1/customers/{customer_id}/points` | Adjust Loyalty Points | 🔒 | AdjustPointsRequest | LoyaltyAccountSchema |
| POST | `/api/cashier/v1/inventory/adjustments` | Create Adjustment | 🔒 | StockAdjustmentCreate | InventoryStockOut |
| GET | `/api/cashier/v1/inventory/movements` | List Movements | 🔒 |  | InventoryMovementOut[] |
| GET | `/api/cashier/v1/inventory/stocks` | List Stocks | 🔒 |  | InventoryStockOut[] |
| POST | `/api/cashier/v1/labels/generate` | Generate Labels | 🔒 | LabelGenerateRequest |  |
| POST | `/api/cashier/v1/payments/aba/khqr` | Create Khqr | 🔒 | CreateKhqrRequest | PaymentTransactionOut |
| POST | `/api/cashier/v1/payments/aba/purchase-form` | Create Purchase Form | 🔒 | CreatePurchaseFormRequest | PurchaseFormOut |
| POST | `/api/cashier/v1/payments/aba/{payment_id}/cancel` | Cancel Payment | 🔒 |  | PaymentTransactionOut |
| GET | `/api/cashier/v1/payments/aba/{payment_id}/status` | Get Payment Status | 🔒 |  | PaymentTransactionOut |
| GET | `/api/cashier/v1/product-variants/` | List Variants | 🔒 |  | ProductVariantOut[] |
| POST | `/api/cashier/v1/product-variants/` | Create Variant | 🔒 | ProductVariantCreate | ProductVariantOut |
| GET | `/api/cashier/v1/product-variants/by-barcode/{barcode}` | Get Variant By Barcode | 🔒 |  | ProductVariantOut |
| GET | `/api/cashier/v1/product-variants/by-qr/{reference}` | Get Variant By Qr | 🔒 |  | ProductVariantOut |
| GET | `/api/cashier/v1/product-variants/by-sku/{sku}` | Get Variant By Sku | 🔒 |  | ProductVariantOut |
| DELETE | `/api/cashier/v1/product-variants/{id}` | Delete Variant | 🔒 |  |  |
| GET | `/api/cashier/v1/product-variants/{id}` | Get Variant | 🔒 |  | ProductVariantOut |
| PATCH | `/api/cashier/v1/product-variants/{id}` | Update Variant | 🔒 | ProductVariantUpdate | ProductVariantOut |
| PUT | `/api/cashier/v1/product-variants/{id}` | Update Variant | 🔒 | ProductVariantUpdate | ProductVariantOut |
| GET | `/api/cashier/v1/product-variants/{id}/barcode` | Get Variant Barcode | 🔒 |  |  |
| GET | `/api/cashier/v1/product-variants/{id}/qr` | Get Variant Qr | 🔒 |  |  |
| GET | `/api/cashier/v1/products/` | List Products | 🔒 |  | ProductPaginationResponse | ProductPaginationWithVariantsResponse |
| POST | `/api/cashier/v1/products/` | Create Product | 🔒 | ProductCreate | ProductOut |
| GET | `/api/cashier/v1/products/{id}` | Get Product | 🔒 |  | ProductWithVariants |
| PATCH | `/api/cashier/v1/products/{id}` | Update Product | 🔒 | ProductUpdate | ProductOut |
| PUT | `/api/cashier/v1/products/{id}` | Update Product | 🔒 | ProductUpdate | ProductOut |
| DELETE | `/api/cashier/v1/products/{id}` | Delete Product | 🔒 |  |  |
| GET | `/api/cashier/v1/products/{id}/variants` | Get Product Variants | 🔒 |  | ProductVariantOut[] |
| GET | `/api/cashier/v1/promotions` | List Promotions | 🔒 |  | PromotionOut[] |
| POST | `/api/cashier/v1/promotions` | Create Promotion | 🔒 | PromotionCreate | PromotionOut |
| POST | `/api/cashier/v1/promotions/validate` | Validate Coupon | 🔒 | CouponValidationRequest | CouponValidationResponse |
| GET | `/api/cashier/v1/promotions/{promo_id}` | Get Promotion | 🔒 |  | PromotionOut |
| PUT | `/api/cashier/v1/promotions/{promo_id}` | Update Promotion | 🔒 | PromotionUpdate | PromotionOut |
| PATCH | `/api/cashier/v1/promotions/{promo_id}` | Update Promotion | 🔒 | PromotionUpdate | PromotionOut |
| DELETE | `/api/cashier/v1/promotions/{promo_id}` | Delete Promotion | 🔒 |  |  |
| GET | `/api/cashier/v1/returns/` | List Returns | 🔒 |  | ReturnOut[] |
| POST | `/api/cashier/v1/returns/` | Create Return | 🔒 | ReturnCreate | ReturnOut |
| GET | `/api/cashier/v1/sales/` | List Sales | 🔒 |  | SaleOut[] |
| POST | `/api/cashier/v1/sales/` | Create Sale | 🔒 | SaleCreate | SaleOut |
| GET | `/api/cashier/v1/sales/{id}` | Get Sale | 🔒 |  | SaleOut |
| POST | `/api/cashier/v1/sales/{id}/cancel` | Cancel Sale | 🔒 |  | SaleOut |
| POST | `/api/cashier/v1/sales/{id}/complete` | Complete Sale | 🔒 | SaleComplete | SaleOut |
| GET | `/api/cashier/v1/scanner/qr` | Generate QR Code image for scanner pairing link | 🔒 |  |  |
| GET | `/api/cashier/v1/scanner/{session_id}/latest` | Get Latest Scans | 🔒 |  |  |
| POST | `/api/cashier/v1/scanner/{session_id}/scan` | Post Scan | 🔒 | ScanPayload |  |
| GET | `/api/cashier/v1/scanner/{session_id}/status` | Get Session Status | 🔒 |  | SessionStatus |
| GET | `/api/cashier/v1/sizes/` | List Sizes | 🔒 |  | SizeOut[] |
| POST | `/api/cashier/v1/sizes/` | Create Size | 🔒 | SizeCreate | SizeOut |
| GET | `/api/cashier/v1/sizes/{id}` | Get Size | 🔒 |  | SizeOut |
| PATCH | `/api/cashier/v1/sizes/{id}` | Update Size | 🔒 | SizeUpdate | SizeOut |
| PUT | `/api/cashier/v1/sizes/{id}` | Update Size | 🔒 | SizeUpdate | SizeOut |
| DELETE | `/api/cashier/v1/sizes/{id}` | Delete Size | 🔒 |  |  |

## `api/payments/aba`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| POST | `/api/payments/aba/pushback` | Aba Pushback |  |  | object |

## `api/store/v1`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| POST | `/api/store/v1/auth/login` | Customer Login |  | LoginRequest | LoginResponse |
| GET | `/api/store/v1/auth/me` | Customer Me | 🔒 |  | object |
| POST | `/api/store/v1/auth/refresh` | Customer Refresh |  | RefreshRequest | TokenResponse |
| POST | `/api/store/v1/auth/register` | Register Customer |  | CustomerRegisterRequest | object |
| GET | `/api/store/v1/catalog/products` | List Public Products |  |  | object |
| GET | `/api/store/v1/catalog/products/{product_id}` | Get Public Product |  |  | object |

## `api/v1/attachments`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/attachments` | List stored attachments |  |  | AttachmentListResponse |
| POST | `/api/v1/attachments/upload` | Upload a single attachment |  |  | AttachmentResponse |
| POST | `/api/v1/attachments/upload-multiple` | Upload multiple attachments |  |  | AttachmentResponse[] |
| GET | `/api/v1/attachments/{object_name}` | Get direct link to attachment |  |  |  |
| DELETE | `/api/v1/attachments/{object_name}` | Delete an attachment |  |  |  |

## `api/v1/auth`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| POST | `/api/v1/auth/change-password` | Change Password | 🔒 | ChangePasswordRequest | object |
| GET | `/api/v1/auth/clients` | List System Clients |  |  | RESPONSE_ENVELOPE_List_SYSTEM_CLIENT_RESPONSE_SCHEMA__ |
| POST | `/api/v1/auth/clients` | Register System Client |  | SYSTEM_CLIENT_CREATE_SCHEMA | RESPONSE_ENVELOPE_API_KEY_CREATED_SCHEMA_ |
| PUT | `/api/v1/auth/clients/{code}/revoke` | Revoke System Client |  |  | RESPONSE_ENVELOPE_SYSTEM_CLIENT_RESPONSE_SCHEMA_ |
| POST | `/api/v1/auth/login` | Login |  | LoginRequest | LoginResponse |
| POST | `/api/v1/auth/logout` | Logout |  | LogoutRequest | object |
| GET | `/api/v1/auth/me` | Get Me | 🔒 |  | UserOut |
| POST | `/api/v1/auth/refresh` | Refresh |  | RefreshRequest | TokenResponse |

## `api/v1/branches`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/branches/` | List Branches | 🔒 |  | BranchOut[] |

## `api/v1/brands`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/brands/` | List Brands | 🔒 |  | BrandOut[] |
| POST | `/api/v1/brands/` | Create Brand | 🔒 | BrandCreate | BrandOut |
| GET | `/api/v1/brands/{id}` | Get Brand | 🔒 |  | BrandOut |
| PATCH | `/api/v1/brands/{id}` | Update Brand | 🔒 | BrandUpdate | BrandOut |
| PUT | `/api/v1/brands/{id}` | Update Brand | 🔒 | BrandUpdate | BrandOut |
| DELETE | `/api/v1/brands/{id}` | Delete Brand | 🔒 |  |  |

## `api/v1/categories`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/categories/` | List Categories | 🔒 |  | CategoryOut[] |
| POST | `/api/v1/categories/` | Create Category | 🔒 | CategoryCreate | CategoryOut |
| GET | `/api/v1/categories/{id}` | Get Category | 🔒 |  | CategoryOut |
| PATCH | `/api/v1/categories/{id}` | Update Category | 🔒 | CategoryUpdate | CategoryOut |
| PUT | `/api/v1/categories/{id}` | Update Category | 🔒 | CategoryUpdate | CategoryOut |
| DELETE | `/api/v1/categories/{id}` | Delete Category | 🔒 |  |  |

## `api/v1/colors`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/colors/` | List Colors | 🔒 |  | ColorOut[] |
| POST | `/api/v1/colors/` | Create Color | 🔒 | ColorCreate | ColorOut |
| GET | `/api/v1/colors/{id}` | Get Color | 🔒 |  | ColorOut |
| PATCH | `/api/v1/colors/{id}` | Update Color | 🔒 | ColorUpdate | ColorOut |
| PUT | `/api/v1/colors/{id}` | Update Color | 🔒 | ColorUpdate | ColorOut |
| DELETE | `/api/v1/colors/{id}` | Delete Color | 🔒 |  |  |

## `api/v1/customers`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/customers/` | List Customers | 🔒 |  | CustomerListResponse |
| POST | `/api/v1/customers/` | Create Customer | 🔒 | CustomerCreate | CustomerResponse |
| GET | `/api/v1/customers/{customer_id}` | Get Customer | 🔒 |  | CustomerResponse |
| PATCH | `/api/v1/customers/{customer_id}` | Update Customer | 🔒 | CustomerUpdate | CustomerResponse |
| PUT | `/api/v1/customers/{customer_id}` | Update Customer | 🔒 | CustomerUpdate | CustomerResponse |
| POST | `/api/v1/customers/{customer_id}/points` | Adjust Loyalty Points | 🔒 | AdjustPointsRequest | LoyaltyAccountSchema |

## `api/v1/expenses`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/expenses` | List Expenses | 🔒 |  | ExpenseOut[] |
| POST | `/api/v1/expenses` | Create Expense | 🔒 | ExpenseCreate | ExpenseOut |
| GET | `/api/v1/expenses/categories` | List Categories | 🔒 |  | ExpenseCategoryOut[] |
| POST | `/api/v1/expenses/categories` | Create Category | 🔒 | ExpenseCategoryCreate | ExpenseCategoryOut |
| PUT | `/api/v1/expenses/categories/{cat_id}` | Update Category | 🔒 | ExpenseCategoryUpdate | ExpenseCategoryOut |
| PATCH | `/api/v1/expenses/categories/{cat_id}` | Update Category | 🔒 | ExpenseCategoryUpdate | ExpenseCategoryOut |
| GET | `/api/v1/expenses/{expense_id}` | Get Expense | 🔒 |  | ExpenseOut |
| PUT | `/api/v1/expenses/{expense_id}` | Update Expense | 🔒 | ExpenseUpdate | ExpenseOut |
| PATCH | `/api/v1/expenses/{expense_id}` | Update Expense | 🔒 | ExpenseUpdate | ExpenseOut |
| POST | `/api/v1/expenses/{expense_id}/approve` | Approve Expense | 🔒 |  | ExpenseOut |
| POST | `/api/v1/expenses/{expense_id}/reject` | Reject Expense | 🔒 |  | ExpenseOut |

## `api/v1/health`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/health` | Health Check |  |  | RESPONSE_ENVELOPE_dict_ |
| GET | `/api/v1/health/ready` | Readiness Check |  |  | RESPONSE_ENVELOPE_dict_ |
| GET | `/api/v1/health/response-codes` | List Response Codes |  |  | RESPONSE_ENVELOPE_List_RESPONSE_CODE_ITEM_SCHEMA__ |

## `api/v1/inventory`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| POST | `/api/v1/inventory/adjustments` | Create Adjustment | 🔒 | StockAdjustmentCreate | InventoryStockOut |
| GET | `/api/v1/inventory/movements` | List Movements | 🔒 |  | InventoryMovementOut[] |
| GET | `/api/v1/inventory/stocks` | List Stocks | 🔒 |  | InventoryStockOut[] |
| GET | `/api/v1/inventory/transfers/` | List Transfers | 🔒 |  | StockTransferOut[] |
| POST | `/api/v1/inventory/transfers/` | Create Transfer | 🔒 | StockTransferCreate | StockTransferOut |
| POST | `/api/v1/inventory/transfers/{id}/approve` | Approve Transfer | 🔒 |  | StockTransferOut |
| POST | `/api/v1/inventory/transfers/{id}/cancel` | Cancel Transfer | 🔒 |  | StockTransferOut |
| POST | `/api/v1/inventory/transfers/{id}/dispatch` | Dispatch Transfer | 🔒 |  | StockTransferOut |
| POST | `/api/v1/inventory/transfers/{id}/receive` | Receive Transfer | 🔒 |  | StockTransferOut |

## `api/v1/labels`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| POST | `/api/v1/labels/generate` | Generate Labels | 🔒 | LabelGenerateRequest |  |

## `api/v1/logs`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/logs/system` | List System Logs |  |  | RESPONSE_ENVELOPE_SYSTEM_LOG_LIST_OUT_SCHEMA_ |
| GET | `/api/v1/logs/telegram-outbound` | List Telegram Outbound Logs |  |  | RESPONSE_ENVELOPE_List_TELEGRAM_OUTBOUND_RESPONSE_SCHEMA__ |

## `api/v1/product-variants`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/product-variants/` | List Variants | 🔒 |  | ProductVariantOut[] |
| POST | `/api/v1/product-variants/` | Create Variant | 🔒 | ProductVariantCreate | ProductVariantOut |
| GET | `/api/v1/product-variants/by-barcode/{barcode}` | Get Variant By Barcode |  |  | ProductVariantOut |
| GET | `/api/v1/product-variants/by-qr/{reference}` | Get Variant By Qr |  |  | ProductVariantOut |
| GET | `/api/v1/product-variants/by-sku/{sku}` | Get Variant By Sku |  |  | ProductVariantOut |
| DELETE | `/api/v1/product-variants/{id}` | Delete Variant | 🔒 |  |  |
| GET | `/api/v1/product-variants/{id}` | Get Variant | 🔒 |  | ProductVariantOut |
| PATCH | `/api/v1/product-variants/{id}` | Update Variant | 🔒 | ProductVariantUpdate | ProductVariantOut |
| PUT | `/api/v1/product-variants/{id}` | Update Variant | 🔒 | ProductVariantUpdate | ProductVariantOut |
| GET | `/api/v1/product-variants/{id}/barcode` | Get Variant Barcode |  |  |  |
| GET | `/api/v1/product-variants/{id}/qr` | Get Variant Qr |  |  |  |

## `api/v1/products`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/products/` | List Products | 🔒 |  | ProductPaginationResponse | ProductPaginationWithVariantsResponse |
| POST | `/api/v1/products/` | Create Product | 🔒 | ProductCreate | ProductOut |
| GET | `/api/v1/products/{id}` | Get Product | 🔒 |  | ProductWithVariants |
| PATCH | `/api/v1/products/{id}` | Update Product | 🔒 | ProductUpdate | ProductOut |
| PUT | `/api/v1/products/{id}` | Update Product | 🔒 | ProductUpdate | ProductOut |
| DELETE | `/api/v1/products/{id}` | Delete Product | 🔒 |  |  |
| GET | `/api/v1/products/{id}/variants` | Get Product Variants | 🔒 |  | ProductVariantOut[] |

## `api/v1/promotions`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/promotions` | List Promotions | 🔒 |  | PromotionOut[] |
| POST | `/api/v1/promotions` | Create Promotion | 🔒 | PromotionCreate | PromotionOut |
| POST | `/api/v1/promotions/validate` | Validate Coupon | 🔒 | CouponValidationRequest | CouponValidationResponse |
| GET | `/api/v1/promotions/{promo_id}` | Get Promotion | 🔒 |  | PromotionOut |
| PUT | `/api/v1/promotions/{promo_id}` | Update Promotion | 🔒 | PromotionUpdate | PromotionOut |
| PATCH | `/api/v1/promotions/{promo_id}` | Update Promotion | 🔒 | PromotionUpdate | PromotionOut |
| DELETE | `/api/v1/promotions/{promo_id}` | Delete Promotion | 🔒 |  |  |

## `api/v1/purchases`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/purchases` | List Purchase Orders | 🔒 |  | PurchaseOrderOut[] |
| POST | `/api/v1/purchases` | Create Purchase Order | 🔒 | PurchaseOrderCreate | PurchaseOrderOut |
| POST | `/api/v1/purchases/receipts` | Create Goods Receipt | 🔒 | GoodsReceiptCreate | GoodsReceiptOut |
| GET | `/api/v1/purchases/receipts/{receipt_id}` | Get Goods Receipt | 🔒 |  | GoodsReceiptOut |
| GET | `/api/v1/purchases/{order_id}` | Get Purchase Order | 🔒 |  | PurchaseOrderOut |
| PATCH | `/api/v1/purchases/{order_id}` | Update Purchase Order | 🔒 | PurchaseOrderUpdate | PurchaseOrderOut |
| POST | `/api/v1/purchases/{order_id}/approve` | Approve Purchase Order | 🔒 |  | PurchaseOrderOut |
| POST | `/api/v1/purchases/{order_id}/cancel` | Cancel Purchase Order | 🔒 |  | PurchaseOrderOut |
| GET | `/api/v1/purchases/{order_id}/receipts` | List Order Receipts | 🔒 |  | GoodsReceiptOut[] |

## `api/v1/reports`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/reports/dashboard` | Dashboard | 🔒 |  | object |
| GET | `/api/v1/reports/inventory` | Inventory Report | 🔒 |  | object |
| GET | `/api/v1/reports/profit` | Profit Report | 🔒 |  | object |
| GET | `/api/v1/reports/purchases` | Purchases Report | 🔒 |  | object |
| GET | `/api/v1/reports/sales` | Sales Report | 🔒 |  | object |

## `api/v1/returns`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/returns/` | List Returns | 🔒 |  | ReturnOut[] |
| POST | `/api/v1/returns/` | Create Return | 🔒 | ReturnCreate | ReturnOut |

## `api/v1/roles`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/roles` | List Roles | 🔒 |  | RoleOut[] |
| POST | `/api/v1/roles` | Create Role | 🔒 | RoleCreate | RoleOut |
| GET | `/api/v1/roles/permissions` | List Permissions | 🔒 |  | PermissionOut[] |
| PUT | `/api/v1/roles/{role_id}` | Update Role | 🔒 | RoleUpdate | RoleOut |
| PATCH | `/api/v1/roles/{role_id}` | Update Role | 🔒 | RoleUpdate | RoleOut |

## `api/v1/sales`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/sales/` | List Sales | 🔒 |  | SaleOut[] |
| POST | `/api/v1/sales/` | Create Sale | 🔒 | SaleCreate | SaleOut |
| GET | `/api/v1/sales/{id}` | Get Sale | 🔒 |  | SaleOut |
| POST | `/api/v1/sales/{id}/cancel` | Cancel Sale | 🔒 |  | SaleOut |
| POST | `/api/v1/sales/{id}/complete` | Complete Sale | 🔒 | SaleComplete | SaleOut |

## `api/v1/scanner`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/scanner/qr` | Generate QR Code image for scanner pairing link |  |  |  |
| GET | `/api/v1/scanner/{session_id}/latest` | Get Latest Scans |  |  |  |
| POST | `/api/v1/scanner/{session_id}/scan` | Post Scan |  | ScanPayload |  |
| GET | `/api/v1/scanner/{session_id}/status` | Get Session Status |  |  | SessionStatus |

## `api/v1/sizes`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/sizes/` | List Sizes | 🔒 |  | SizeOut[] |
| POST | `/api/v1/sizes/` | Create Size | 🔒 | SizeCreate | SizeOut |
| GET | `/api/v1/sizes/{id}` | Get Size | 🔒 |  | SizeOut |
| PATCH | `/api/v1/sizes/{id}` | Update Size | 🔒 | SizeUpdate | SizeOut |
| PUT | `/api/v1/sizes/{id}` | Update Size | 🔒 | SizeUpdate | SizeOut |
| DELETE | `/api/v1/sizes/{id}` | Delete Size | 🔒 |  |  |

## `api/v1/suppliers`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/suppliers/` | List Suppliers | 🔒 |  | SupplierOut[] |
| POST | `/api/v1/suppliers/` | Create Supplier | 🔒 | SupplierCreate | SupplierOut |
| GET | `/api/v1/suppliers/{id}` | Get Supplier | 🔒 |  | SupplierOut |
| PATCH | `/api/v1/suppliers/{id}` | Update Supplier | 🔒 | SupplierUpdate | SupplierOut |
| PUT | `/api/v1/suppliers/{id}` | Update Supplier | 🔒 | SupplierUpdate | SupplierOut |
| DELETE | `/api/v1/suppliers/{id}` | Delete Supplier | 🔒 |  |  |

## `api/v1/systems`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/systems` | List Systems |  |  | RESPONSE_ENVELOPE_SYSTEM_LIST_OUT_SCHEMA_ |
| POST | `/api/v1/systems` | Create System |  | SYSTEM_CREATE_SCHEMA | RESPONSE_ENVELOPE_SYSTEM_RESPONSE_SCHEMA_ |
| PUT | `/api/v1/systems/endpoints/{endpoint_id}` | Update System Endpoint |  | SYSTEM_ENDPOINT_UPDATE_SCHEMA | RESPONSE_ENVELOPE_SYSTEM_ENDPOINT_RESPONSE_SCHEMA_ |
| DELETE | `/api/v1/systems/endpoints/{endpoint_id}` | Delete System Endpoint |  |  |  |
| GET | `/api/v1/systems/{code}` | Get System |  |  | RESPONSE_ENVELOPE_SYSTEM_RESPONSE_SCHEMA_ |
| PUT | `/api/v1/systems/{code}` | Update System |  | SYSTEM_UPDATE_SCHEMA | RESPONSE_ENVELOPE_SYSTEM_RESPONSE_SCHEMA_ |
| DELETE | `/api/v1/systems/{code}` | Delete System |  |  |  |
| GET | `/api/v1/systems/{code}/credentials` | List System Credentials |  |  | RESPONSE_ENVELOPE_List_SYSTEM_CREDENTIAL_RESPONSE_SCHEMA__ |
| POST | `/api/v1/systems/{code}/credentials` | Create System Credential |  | SYSTEM_CREDENTIAL_CREATE_SCHEMA | RESPONSE_ENVELOPE_SYSTEM_CREDENTIAL_RESPONSE_SCHEMA_ |
| GET | `/api/v1/systems/{code}/endpoints` | List System Endpoints |  |  | RESPONSE_ENVELOPE_List_SYSTEM_ENDPOINT_RESPONSE_SCHEMA__ |
| POST | `/api/v1/systems/{code}/endpoints` | Create System Endpoint |  | SYSTEM_ENDPOINT_CREATE_SCHEMA | RESPONSE_ENVELOPE_SYSTEM_ENDPOINT_RESPONSE_SCHEMA_ |

## `api/v1/telegram`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/telegram/bots` | List Telegram Bots |  |  | RESPONSE_ENVELOPE_TELEGRAM_BOT_LIST_OUT_SCHEMA_ |
| POST | `/api/v1/telegram/bots` | Create Telegram Bot |  | TELEGRAM_BOT_CREATE_SCHEMA | RESPONSE_ENVELOPE_TELEGRAM_BOT_RESPONSE_SCHEMA_ |
| GET | `/api/v1/telegram/bots/{bot_id}` | Get Telegram Bot |  |  | RESPONSE_ENVELOPE_TELEGRAM_BOT_RESPONSE_SCHEMA_ |
| PUT | `/api/v1/telegram/bots/{bot_id}` | Update Telegram Bot |  | TELEGRAM_BOT_UPDATE_SCHEMA | RESPONSE_ENVELOPE_TELEGRAM_BOT_RESPONSE_SCHEMA_ |
| DELETE | `/api/v1/telegram/bots/{bot_id}` | Delete Telegram Bot |  |  |  |
| GET | `/api/v1/telegram/chats` | List Telegram Chats |  |  | RESPONSE_ENVELOPE_TELEGRAM_CHAT_LIST_OUT_SCHEMA_ |
| POST | `/api/v1/telegram/chats` | Create Telegram Chat |  | TELEGRAM_CHAT_CREATE_SCHEMA | RESPONSE_ENVELOPE_TELEGRAM_CHAT_RESPONSE_SCHEMA_ |
| GET | `/api/v1/telegram/chats/{chat_id}` | Get Telegram Chat |  |  | RESPONSE_ENVELOPE_TELEGRAM_CHAT_RESPONSE_SCHEMA_ |
| PUT | `/api/v1/telegram/chats/{chat_id}` | Update Telegram Chat |  | TELEGRAM_CHAT_UPDATE_SCHEMA | RESPONSE_ENVELOPE_TELEGRAM_CHAT_RESPONSE_SCHEMA_ |
| DELETE | `/api/v1/telegram/chats/{chat_id}` | Delete Telegram Chat |  |  |  |
| POST | `/api/v1/telegram/send` | Send Telegram Message |  | TELEGRAM_SEND_MESSAGE_SCHEMA | RESPONSE_ENVELOPE_Dict_str__Any__ |

## `api/v1/users`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/users` | List Users | 🔒 |  | UserOut[] |
| POST | `/api/v1/users` | Create User | 🔒 | UserCreate | UserOut |
| GET | `/api/v1/users/{user_id}` | Get User | 🔒 |  | UserOut |
| PUT | `/api/v1/users/{user_id}` | Update User | 🔒 | UserUpdate | UserOut |
| PATCH | `/api/v1/users/{user_id}` | Update User | 🔒 | UserUpdate | UserOut |
| DELETE | `/api/v1/users/{user_id}` | Deactivate User | 🔒 |  | UserOut |

## `health`

| Method | Path | Summary | Auth | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/health` | Root Health Check |  |  | object |
