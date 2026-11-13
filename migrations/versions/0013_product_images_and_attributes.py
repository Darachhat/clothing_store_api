"""Add product tags, product_images, and configurable product_attributes tables.

Revision ID: 0013_product_images_and_attributes
Revises: 0012_telegram_bot_login_url
Create Date: 2026-11-13 22:05:00.000000
"""
from __future__ import annotations

from alembic import op

revision      = "0013_product_images_and_attributes"
down_revision = "0012_telegram_bot_login_url"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.execute(
        """
        -- 1. Add tags JSONB array to data.products
        ALTER TABLE data.products
        ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '[]'::jsonb;

        -- 2. Create data.product_images
        CREATE TABLE IF NOT EXISTS data.product_images (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id UUID NOT NULL REFERENCES data.products(id) ON DELETE CASCADE,
            variant_id UUID REFERENCES data.product_variants(id) ON DELETE SET NULL,
            image_url VARCHAR(500) NOT NULL,
            is_primary BOOLEAN NOT NULL DEFAULT FALSE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            status_code VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
            created_datetime TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_datetime TIMESTAMPTZ DEFAULT NOW(),
            deleted_datetime TIMESTAMPTZ,
            created_by VARCHAR(100),
            updated_by VARCHAR(100),
            deleted_by VARCHAR(100)
        );

        CREATE INDEX IF NOT EXISTS ix_product_images_product_id ON data.product_images (product_id);
        CREATE INDEX IF NOT EXISTS ix_product_images_variant_id ON data.product_images (variant_id);

        -- Backfill primary images from existing data.products.image_url
        INSERT INTO data.product_images (id, product_id, image_url, is_primary, sort_order, status_code)
        SELECT gen_random_uuid(), p.id, p.image_url, TRUE, 0, 'ACTIVE'
        FROM data.products p
        WHERE p.image_url IS NOT NULL
          AND p.image_url <> ''
          AND NOT EXISTS (
              SELECT 1 FROM data.product_images pi WHERE pi.product_id = p.id
          );

        -- 3. Create base_data.product_attributes
        CREATE TABLE IF NOT EXISTS base_data.product_attributes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code VARCHAR(100) NOT NULL UNIQUE,
            name VARCHAR(200) NOT NULL,
            display_name VARCHAR(200) NOT NULL,
            attribute_type VARCHAR(50) NOT NULL DEFAULT 'SELECT',
            sort_order INTEGER NOT NULL DEFAULT 0,
            status_code VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
            created_datetime TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_datetime TIMESTAMPTZ DEFAULT NOW(),
            deleted_datetime TIMESTAMPTZ,
            created_by VARCHAR(100),
            updated_by VARCHAR(100),
            deleted_by VARCHAR(100)
        );

        CREATE INDEX IF NOT EXISTS ix_product_attributes_code ON base_data.product_attributes (code);

        -- 4. Create base_data.product_attribute_values
        CREATE TABLE IF NOT EXISTS base_data.product_attribute_values (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            attribute_id UUID NOT NULL REFERENCES base_data.product_attributes(id) ON DELETE CASCADE,
            value VARCHAR(200) NOT NULL,
            display_value VARCHAR(200) NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            status_code VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
            created_datetime TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_datetime TIMESTAMPTZ DEFAULT NOW(),
            deleted_datetime TIMESTAMPTZ,
            created_by VARCHAR(100),
            updated_by VARCHAR(100),
            deleted_by VARCHAR(100),
            CONSTRAINT uq_product_attr_value UNIQUE (attribute_id, value)
        );

        CREATE INDEX IF NOT EXISTS ix_product_attribute_values_attribute_id ON base_data.product_attribute_values (attribute_id);

        -- 5. Create data.product_attribute_assignments
        CREATE TABLE IF NOT EXISTS data.product_attribute_assignments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id UUID NOT NULL REFERENCES data.products(id) ON DELETE CASCADE,
            attribute_id UUID NOT NULL REFERENCES base_data.product_attributes(id) ON DELETE CASCADE,
            attribute_value_id UUID NOT NULL REFERENCES base_data.product_attribute_values(id) ON DELETE CASCADE,
            status_code VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
            created_datetime TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_datetime TIMESTAMPTZ DEFAULT NOW(),
            deleted_datetime TIMESTAMPTZ,
            created_by VARCHAR(100),
            updated_by VARCHAR(100),
            deleted_by VARCHAR(100),
            CONSTRAINT uq_product_attr_assignment UNIQUE (product_id, attribute_id, attribute_value_id)
        );

        CREATE INDEX IF NOT EXISTS ix_product_attr_assign_product_id ON data.product_attribute_assignments (product_id);
        CREATE INDEX IF NOT EXISTS ix_product_attr_assign_attribute_id ON data.product_attribute_assignments (attribute_id);

        -- 6. Seed default KVC apparel attributes & values
        INSERT INTO base_data.product_attributes (id, code, name, display_name, attribute_type, sort_order, status_code)
        VALUES
            (gen_random_uuid(), 'gender',   'Gender',   'Gender',   'SELECT', 1, 'ACTIVE'),
            (gen_random_uuid(), 'fit',      'Fit',      'Fit',      'SELECT', 2, 'ACTIVE'),
            (gen_random_uuid(), 'material', 'Material', 'Material', 'SELECT', 3, 'ACTIVE'),
            (gen_random_uuid(), 'pattern',  'Pattern',  'Pattern',  'SELECT', 4, 'ACTIVE'),
            (gen_random_uuid(), 'season',   'Season',   'Season',   'SELECT', 5, 'ACTIVE')
        ON CONFLICT (code) DO NOTHING;

        -- Seed Gender values
        INSERT INTO base_data.product_attribute_values (id, attribute_id, value, display_value, sort_order, status_code)
        SELECT gen_random_uuid(), a.id, v.val, v.disp, v.ord, 'ACTIVE'
        FROM base_data.product_attributes a
        CROSS JOIN (
            VALUES
                ('UNISEX', 'Unisex', 1),
                ('MEN',    'Men',    2),
                ('WOMEN',  'Women',  3),
                ('KIDS',   'Kids',   4)
        ) AS v(val, disp, ord)
        WHERE a.code = 'gender'
        ON CONFLICT (attribute_id, value) DO NOTHING;

        -- Seed Fit values
        INSERT INTO base_data.product_attribute_values (id, attribute_id, value, display_value, sort_order, status_code)
        SELECT gen_random_uuid(), a.id, v.val, v.disp, v.ord, 'ACTIVE'
        FROM base_data.product_attributes a
        CROSS JOIN (
            VALUES
                ('REGULAR',  'Regular Fit',  1),
                ('OVERSIZE', 'Oversize Fit', 2),
                ('SLIM',     'Slim Fit',     3),
                ('RELAXED',  'Relaxed Fit',  4),
                ('CROPPED',  'Cropped',      5)
        ) AS v(val, disp, ord)
        WHERE a.code = 'fit'
        ON CONFLICT (attribute_id, value) DO NOTHING;

        -- Seed Material values
        INSERT INTO base_data.product_attribute_values (id, attribute_id, value, display_value, sort_order, status_code)
        SELECT gen_random_uuid(), a.id, v.val, v.disp, v.ord, 'ACTIVE'
        FROM base_data.product_attributes a
        CROSS JOIN (
            VALUES
                ('COTTON_100',   '100% Cotton',      1),
                ('COTTON_BLEND', 'Cotton Blend',     2),
                ('LINEN',        'Linen',            3),
                ('DENIM',        'Denim',            4),
                ('POLYESTER',    'Polyester',        5),
                ('SILK',         'Silk / Satin',     6),
                ('FLEECE',       'Fleece / Knit',    7)
        ) AS v(val, disp, ord)
        WHERE a.code = 'material'
        ON CONFLICT (attribute_id, value) DO NOTHING;

        -- Seed Pattern values
        INSERT INTO base_data.product_attribute_values (id, attribute_id, value, display_value, sort_order, status_code)
        SELECT gen_random_uuid(), a.id, v.val, v.disp, v.ord, 'ACTIVE'
        FROM base_data.product_attributes a
        CROSS JOIN (
            VALUES
                ('SOLID',   'Solid / Plain', 1),
                ('GRAPHIC', 'Graphic Print', 2),
                ('STRIPED', 'Striped',       3),
                ('PLAID',   'Plaid / Check', 4),
                ('FLORAL',  'Floral',        5)
        ) AS v(val, disp, ord)
        WHERE a.code = 'pattern'
        ON CONFLICT (attribute_id, value) DO NOTHING;

        -- Seed Season values
        INSERT INTO base_data.product_attribute_values (id, attribute_id, value, display_value, sort_order, status_code)
        SELECT gen_random_uuid(), a.id, v.val, v.disp, v.ord, 'ACTIVE'
        FROM base_data.product_attributes a
        CROSS JOIN (
            VALUES
                ('ALL_SEASON', 'All Season',          1),
                ('SS',         'Spring / Summer',     2),
                ('FW',         'Fall / Winter',       3),
                ('RESORT',     'Holiday / Collection', 4)
        ) AS v(val, disp, ord)
        WHERE a.code = 'season'
        ON CONFLICT (attribute_id, value) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS data.product_attribute_assignments CASCADE;
        DROP TABLE IF EXISTS base_data.product_attribute_values CASCADE;
        DROP TABLE IF EXISTS base_data.product_attributes CASCADE;
        DROP TABLE IF EXISTS data.product_images CASCADE;
        ALTER TABLE data.products DROP COLUMN IF EXISTS tags;
        """
    )

