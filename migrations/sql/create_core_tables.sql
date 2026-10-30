-- =============================================================================
-- Core Schemas and Tables Initialization Script (`clothing_store_api`)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS base_data;
CREATE SCHEMA IF NOT EXISTS track;

-- -----------------------------------------------------------------------------
-- 1. `base_data` Schema Tables
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS base_data.translate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ref_id UUID NOT NULL,
    schema_name VARCHAR(100) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    column_name VARCHAR(100) NOT NULL,
    en TEXT,
    km TEXT,
    cn TEXT,
    jp TEXT,
    kr TEXT,
    note TEXT,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS base_data.status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    translate_id UUID,
    description TEXT,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS base_data.auth_type (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS base_data.language (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    native_name VARCHAR(100),
    sort_order INTEGER DEFAULT 0,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS base_data.currency (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    symbol VARCHAR(10),
    decimal_places INTEGER DEFAULT 2 NOT NULL,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

-- Seed initial master data
INSERT INTO base_data.status (code, name, description) VALUES
    ('active', 'Active Status', 'Resource is active and operational'),
    ('inactive', 'Inactive Status', 'Resource is currently disabled'),
    ('pending', 'Pending Status', 'Resource is awaiting verification'),
    ('draft', 'Draft Status', 'Resource is in draft state'),
    ('archived', 'Archived Status', 'Resource has been archived'),
    ('deleted', 'Deleted Status', 'Resource has been soft-deleted')
ON CONFLICT (code) DO NOTHING;

INSERT INTO base_data.auth_type (code, name, description) VALUES
    ('basic', 'HTTP Basic Auth', 'Username and Password authentication'),
    ('bearer', 'HTTP Bearer Token', 'Bearer token authorization header'),
    ('api_key', 'API Key Auth', 'Custom header or query parameter key'),
    ('oauth2', 'OAuth2 Client Credentials', 'OAuth2 token endpoint authorization')
ON CONFLICT (code) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 2. `auth` Schema Tables
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS auth.system (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    base_url VARCHAR(500),
    scope VARCHAR(50) DEFAULT 'external' NOT NULL,
    is_encrypted_body BOOLEAN DEFAULT FALSE NOT NULL,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS auth.system_client (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    api_key_hash VARCHAR(255) NOT NULL,
    description TEXT,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS auth.system_credential (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_code VARCHAR(100) NOT NULL,
    description TEXT,
    traffic_type VARCHAR(20) NOT NULL,
    auth_type_code VARCHAR(50) NOT NULL,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS auth.credential_basic (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_code VARCHAR(100) NOT NULL,
    traffic_type VARCHAR(20) NOT NULL,
    username VARCHAR(255) NOT NULL,
    password TEXT NOT NULL,
    description TEXT,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS auth.credential_bearer (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_code VARCHAR(100) NOT NULL,
    traffic_type VARCHAR(20) NOT NULL,
    header_name VARCHAR(100) DEFAULT 'Authorization' NOT NULL,
    token_prefix VARCHAR(50) DEFAULT 'Bearer' NOT NULL,
    token_value TEXT NOT NULL,
    description TEXT,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS auth.credential_api_key (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_code VARCHAR(100) NOT NULL,
    traffic_type VARCHAR(20) NOT NULL,
    key_location VARCHAR(20) DEFAULT 'header' NOT NULL,
    key_name VARCHAR(100) NOT NULL,
    key_value TEXT NOT NULL,
    description TEXT,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS auth.credential_oauth2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_code VARCHAR(100) NOT NULL,
    traffic_type VARCHAR(20) NOT NULL,
    token_url VARCHAR(500),
    grant_type VARCHAR(100),
    client_id VARCHAR(255),
    client_secret TEXT,
    username VARCHAR(255),
    password TEXT,
    description TEXT,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS auth.telegram_bot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    user_id VARCHAR(100),
    username VARCHAR(100),
    token TEXT,
    description TEXT,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS auth.telegram_chat (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) NOT NULL UNIQUE,
    telegram_bot_code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50),
    link VARCHAR(500),
    chat_id VARCHAR(100),
    thread_id VARCHAR(100),
    description TEXT,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS auth.system_endpoint (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_code VARCHAR(100) NOT NULL,
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    operation_type VARCHAR(50),
    endpoint VARCHAR(500) NOT NULL,
    http_method VARCHAR(10) DEFAULT 'POST' NOT NULL,
    traffic_type VARCHAR(20) DEFAULT 'outbound' NOT NULL,
    request_timeout INTEGER DEFAULT 30 NOT NULL,
    headers_config JSONB,
    query_config JSONB,
    description TEXT,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

-- -----------------------------------------------------------------------------
-- 3. `track` Schema Tables
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS track.system_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_log_id VARCHAR(40),
    traffic_type VARCHAR(20),
    system_code VARCHAR(100),
    channel VARCHAR(50),
    request_method VARCHAR(10) NOT NULL,
    request_endpoint TEXT NOT NULL,
    request_netloc VARCHAR(255),
    request_content_type VARCHAR(255),
    request_user_agent TEXT,
    request_headers JSONB,
    request_body JSONB,
    requested_datetime TIMESTAMP WITHOUT TIME ZONE,
    client_ip VARCHAR(50),
    response_code INTEGER,
    response_headers JSONB,
    response_body JSONB,
    response_duration NUMERIC,
    response_datetime TIMESTAMP WITHOUT TIME ZONE,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS track.telegram_outbound (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_chat_code VARCHAR(100),
    chat_type VARCHAR(50),
    telegram_bot_code VARCHAR(100),
    chat_id VARCHAR(100),
    thread_id VARCHAR(100),
    request_object JSONB,
    response_object JSONB,
    is_success BOOLEAN DEFAULT TRUE NOT NULL,
    telegram_message_id VARCHAR(100),
    error_code INTEGER,
    error_detail TEXT,
    status_code VARCHAR(10) DEFAULT 'active' NOT NULL,
    created_datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_datetime TIMESTAMP WITHOUT TIME ZONE,
    deleted_datetime TIMESTAMP WITHOUT TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_by VARCHAR(100)
);

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_system_log_traffic ON track.system_log (traffic_type);
CREATE INDEX IF NOT EXISTS idx_system_log_system ON track.system_log (system_code);
CREATE INDEX IF NOT EXISTS idx_system_endpoint_sys ON auth.system_endpoint (system_code);

