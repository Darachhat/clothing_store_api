# Agent Execution Blueprint & Developer Skill Manual — `clothing_store_api`

This document provides step-by-step Standard Operating Procedures (SOP) and strict code formatting rules for software engineers and AI coding agents when expanding or maintaining `clothing_store_api`.

---

## Code Formatting & Spacing Rules

All Python code written in this repository MUST strictly follow these formatting, spacing, and alignment standards:

### 1. Mandatory ALL-CAPS UPPERCASE Class Naming Standard
- **ALL Classes across the codebase MUST be named in ALL CAPS UPPERCASE** (using `UPPERCASE_SNAKE_CASE` or `UPPERCASE`).
- Examples:
  - **ORM Models**: `SYSTEM_MODEL`, `SYSTEM_CLIENT_MODEL`, `CREDENTIAL_BASIC_MODEL`, `SYSTEM_LOG_MODEL`
  - **Pydantic Schemas**: `RESPONSE_ENVELOPE`, `PAGINATED_DATA`, `SYSTEM_CLIENT_CREATE_SCHEMA`, `SYSTEM_CLIENT_RESPONSE_SCHEMA`
  - **Service Layer**: `BASE_SERVICE`, `AUTH_SERVICE`, `PRODUCT_SERVICE`, `PAYMENT_SERVICE`, `SYSTEM_SERVICE`, `TELEGRAM_SERVICE`, `LOG_SERVICE`, `EXTERNAL_SERVICE`
  - **Middlewares**: `TRACE_MIDDLEWARE`, `BASE_MIDDLEWARE`, `SYSTEM_AUTH_MIDDLEWARE`, `AUTH_CONTEXT`
  - **Core Utilities**: `HTTP_CLIENT`, `APP_SCHEDULER`, `SETTINGS`, `INTERCEPT_HANDLER`, `TRACE_LOGGER`
  - **Exceptions**: `APP_EXCEPTION`, `NOT_FOUND_EXCEPTION`, `VALIDATION_EXCEPTION`, `UNAUTHORIZED_EXCEPTION`
  - **Enums**: `ENVIRONMENT_ENUM`, `RESPONSE_CODE_ENUM`, `SYSTEM_CODE_ENUM`

### 2. Primary Keys & Standard Model Fields
- **Primary Keys**: Use UUID primary keys: `id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)`.
- **Table Names**: Use singular snake_case in `auth`, `base_data`, and `track` schemas (e.g. `__tablename__ = "system_client"`).
- **Core Standard Fields**:
  - `code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)`
  - `name: Mapped[str] = mapped_column(String(255), nullable=False)`
  - `status_code: Mapped[str] = mapped_column(String(10), default="active", nullable=False)`

### 3. Vertical Visual Alignment & Spacing Rules
- **Column & Attribute Alignment**:
  - Align variable names, type hint colons (`:`), and assignment operators (`=`) into clean vertical columns within class declarations, models, and dictionaries.
  ```python
  # CORRECT:
  id          : Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  code        : Mapped[str]               = mapped_column(String(100), unique=True, index=True, nullable=False)
  name        : Mapped[str]               = mapped_column(String(255), nullable=False)
  description : Mapped[Optional[str]]     = mapped_column(Text, nullable=True)
  status_code : Mapped[str]               = mapped_column(String(10), default="active", nullable=False)
  ```

- **Leading Comma Format (` , `) in Multi-line Function Calls & Keyword Arguments**:
  - For multi-line function calls, place the comma at the beginning of subsequent lines `, param = value` aligned vertically under the first argument line.
  ```python
  # CORRECT:
  result = HTTP_CLIENT.post(
      url           = target_url
      , data        = payload
      , headers     = req_headers
      , timeout     = 30
      , system_code = "moi_api"
  )
  ```

- **Single-Line Spacing & Operators**:
  - Always include 1 space after commas in single-line argument lists: `func(param1, param2, param3)`.
  - Always place 1 space around binary operators (`+`, `-`, `*`, `/`, `==`, `!=`, `=`, `in`, `is`).
  - Never place spaces inside parentheses or brackets: `[1, 2, 3]`, `func(x, y)`.
  - Indentation: Use 4 spaces for indentation. Never use tabs.
  - Blank Lines: Place 2 blank lines between top-level classes and functions; 1 blank line between class methods.

---

## System, Auth Credentials, Telegram, Base Data & Tracking Architecture

The platform architecture includes these core schemas alongside the `public` clothing store domain schema:

### 1. `auth` Schema (Authentication & Credentials Infrastructure)
- **`system` (`SYSTEM_MODEL`)**: Systems connecting to or exposed by the API hub.
- **`system_client` (`SYSTEM_CLIENT_MODEL`)**: Registered system API clients (`code`, `name`, `api_key_hash`, `status_code`).
- **`system_credential` (`SYSTEM_CREDENTIAL_MODEL`)**: Core credential mapping associating a `system_code`, `traffic_type` (`inbound`/`outbound`), and `auth_type_code`.
- **`credential_basic` (`CREDENTIAL_BASIC_MODEL`)**: Username & Password credentials.
- **`credential_bearer` (`CREDENTIAL_BEARER_MODEL`)**: Static/Dynamic Bearer token configuration (`header_name`, `token_prefix`, `token_value`).
- **`credential_api_key` (`CREDENTIAL_API_KEY_MODEL`)**: API Key credentials (`key_location`, `key_name`, `key_value`).
- **`credential_oauth2` (`CREDENTIAL_OAUTH2_MODEL`)**: OAuth2 credentials (`token_url`, `grant_type`, `client_id`, `client_secret`, `username`, `password`).
- **`telegram_bot` (`TELEGRAM_BOT_MODEL`)**: Bot tokens and identity.
- **`telegram_chat` (`TELEGRAM_CHAT_MODEL`)**: Target channels, groups, or topics.
- **`system_endpoint` (`SYSTEM_ENDPOINT_MODEL`)**: Registry of internal and external HTTP endpoints (`system_code`, `http_method`, `endpoint`, `traffic_type`, `request_timeout`, headers/query configs).

### 2. `base_data` Schema (Reference Master Data)
- **`translate` (`TRANSLATE_MODEL`)**: Multilingual translations (`kh`, `en`, `zh`).
- **`status` (`STATUS_MODEL`)**: Master lookup for status codes (`active`, `inactive`, `pending`, `archived`) linked to `translate`.
- **`auth_type` (`AUTH_TYPE_MODEL`)**: Master lookup for authentication types (`basic`, `bearer`, `api_key`, `oauth2`).
- **`language` (`LANGUAGE_MODEL`)**: Master lookup for language codes and flags.
- **`currency` (`CURRENCY_MODEL`)**: Master lookup for currency codes and symbols.

### 3. `track` Schema (Traffic Audit & Observability)
- **`system_log` (`SYSTEM_LOG_MODEL`)**: Central audit log capturing all `inbound` and `outbound` HTTP traffic (`channel`, redacted headers, JSON request/response bodies, status codes, latency).
- **`telegram_outbound` (`TELEGRAM_OUTBOUND_MODEL`)**: Outbound Telegram message audit log.

