-- 002_customers.sql
-- Customers table in prosauai schema with RLS via prosauai_ops.tenant_id()

CREATE TABLE prosauai.customers (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   UUID NOT NULL,
    phone_hash  VARCHAR(64) NOT NULL,  -- SHA-256 hash, never raw phone
    display_name VARCHAR(255),
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_customer_tenant_phone UNIQUE (tenant_id, phone_hash)
);

CREATE INDEX idx_customers_tenant ON prosauai.customers(tenant_id);

ALTER TABLE prosauai.customers ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON prosauai.customers
    USING (tenant_id = prosauai_ops.tenant_id());
