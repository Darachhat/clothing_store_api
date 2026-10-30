# Developer & Agent Guide — Clothing Store Enterprise FastAPI (`clothing_store_api`)

> [!IMPORTANT]
> **Read this document before writing code, modifying architecture, or adding endpoints to this repository.**
> This is the single authoritative reference for human software engineers and AI coding agents operating on this codebase.

---

## 1. Project Identity & Architecture

`clothing_store_api` is a production-grade, enterprise-ready **FastAPI application** built on the `templete_api` architecture for high reliability, strict layer separation, asynchronous resilience, and observability.

### Core Architectural Principles

1. **Strict Layering**: Code is separated into distinct, decoupled boundaries:
   - **`app/api/`**: HTTP Transport Layer (Routing, Request Parsing, Dependency Injection, Response Serialization). No business rules or DB queries here.
   - **`app/services/`**: Business Logic Layer (Domain rules, orchestration, transaction boundaries, background task trigger).
   - **`app/repositories/`**: Data Access Helper Layer for async domain repositories.
   - **`app/models/`**: Persistence Layer (SQLAlchemy ORM Entities across `public`, `auth`, `base_data`, and `track` schemas).
   - **`app/schemas/`**: Data Contract Layer (Pydantic v2 DTOs for request/response validation).
   - **`app/middleware/`**: Cross-cutting Concerns (Trace logging, CORS, System Auth validation, Access audit logging, Error envelope formatting).
   - **`app/core/`**: Infrastructure & Configurations (Settings, Database Engine, Logging, Celery, Scheduler, Enums, Utilities).
   - **`app/tasks/`**: Asynchronous Background Execution (Task Dispatcher, Celery Workers, APScheduler, Fire-and-forget AsyncIO).

2. **Stateless Application Server**:
   - The application server maintains no in-memory state across requests.
   - Session data, rate limits, and async jobs rely on PostgreSQL, Redis, or Celery.

3. **Dependency Injection**:
   - Database sessions (`get_db`), configuration (`settings`), and authentication contexts (`get_auth_context`, `get_current_active_user`) are injected into endpoints using FastAPI `Depends()`.

4. **Strict Typing & Async Defaults**:
   - All function parameters and return types must be fully typed.
   - External network calls and I/O tasks must use async mechanisms (`httpx`, `AsyncSession` or background workers).

---

## 2. Technology Stack & Key Dependencies

* **Framework:** FastAPI `0.112+` (Python 3.11+, run via `uvicorn`)
* **ORM:** SQLAlchemy `2.0+` (`create_engine`, `create_async_engine`, `sessionmaker`, declarative models)
* **Database:** PostgreSQL (via `psycopg2-binary` and `asyncpg`)
* **Migrations:** Alembic `1.13+`
* **Validation:** Pydantic v2 (`pydantic>=2.9.2`, `pydantic-settings>=2.4.0`)
* **Logging:** `loguru` (Intercepting standard logging, Uvicorn logs, `trace.log`, and daily log rotation)
* **HTTP Client:** `httpx` (`HTTP_CLIENT` async & sync wrappers with retries, global pool, and `track.system_log` outbound auditing)
* **Task Management**:
  * `asyncio.create_task` — Lightweight fire-and-forget in-process background tasks.
  * `Celery` — Heavy, persistent distributed task processing (RabbitMQ / Redis broker).
  * `APScheduler` (`AsyncIOScheduler`) — In-app cron/interval scheduled tasks.
* **Testing:** Pytest (`pytest`, `httpx` AsyncClient & TestClient)

---

## 3. Request Lifecycle & Response Envelopes

### Request Flow
```
Client Request
   │
   ▼
[TRACE_MIDDLEWARE] ────────(Assigns X-Request-ID, writes structured request/response trace to logs/trace.log)
   │
   ▼
[CORSMiddleware]
   │
   ▼
[SYSTEM_AUTH_MIDDLEWARE] ──(Validates API Key / Header -> Injects AUTH_CONTEXT into request.state.auth)
   │
   ▼
[BASE_MIDDLEWARE] ─────────(Captures timing, writes inbound traffic audit to track.system_log, formats unhandled errors)
   │
   ▼
[FastAPI Router & Handler] ──(Validates Schema -> Injects get_db -> Calls Service)
   │
   ▼
[Service Layer] ──────────(Executes DB Transaction / External API Call / Async Tasks)
   │
   ▼
Response Envelope ────────(Standardized JSON output)
```

### Standard Response Format

All template API responses follow the standard JSON envelope (`RESPONSE_ENVELOPE`):

```json
{
  "code": "00000",
  "http_status": 200,
  "message": "Operation completed successfully.",
  "data": { ... },
  "errors": null,
  "request_id": "req_123456789"
}
```

---

## 4. Agent Coding Rules & Strict Constraints

1. **Mandatory ALL-CAPS UPPERCASE Class Naming**: New and template-aligned classes across the codebase (models, schemas, services, middlewares, utilities, exceptions, enums, settings) MUST use `UPPERCASE_SNAKE_CASE` or `UPPERCASE` naming (e.g. `SYSTEM_CLIENT_MODEL`, `AUTH_SERVICE`, `PRODUCT_SERVICE`, `RESPONSE_ENVELOPE`, `BASE_MIDDLEWARE`, `HTTP_CLIENT`), providing backward-compatible aliases where needed by existing callers.
2. **Strict Attribute & Column Vertical Alignment**: Align attribute names, type hint colons (`:`), and assignment operators (`=`) vertically within class definitions, models, and dictionaries.
3. **Leading Comma Format (` , `) in Multi-line Function Calls**: Use leading comma alignment `, param = value` for multi-line keyword argument and function calls.
4. **Spacing Rules**: Always include 1 space after commas in single-line argument lists (`func(a, b, c)`). Always place 1 space around binary operators. Never place spaces inside parentheses or brackets.
5. **No Print Statements**: Always use `from app.core.logger import logger` and log with structured contextual context.
6. **Never Swallow Exceptions**: Handle exceptions explicitly. Return structured error envelopes or throw domain-specific `APP_EXCEPTION` subclasses.
7. **No Direct Model Manipulation in Handlers**: Handlers MUST delegate business logic and persistence to the `services` layer.
8. **Environment Variables via Pydantic Settings**: Do not use `os.getenv` directly inside application modules; read from `settings`.
9. **Always Run Tests After Code Modifications**: Validate changes using `pytest`.

