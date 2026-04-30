-- ============================================================
--  VisaTrack SaaS — Schéma PostgreSQL complet
--  Version 1.0 — MVP Production Ready
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";      -- recherche full-text
CREATE EXTENSION IF NOT EXISTS "btree_gin";    -- index GIN sur colonnes standard

-- ============================================================
-- 1. UTILISATEURS & AUTH
-- ============================================================

CREATE TYPE user_role AS ENUM ('client', 'agent', 'admin', 'superadmin');
CREATE TYPE plan_type AS ENUM ('free', 'premium', 'vip');
CREATE TYPE plan_status AS ENUM ('active', 'cancelled', 'expired', 'trial');

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    phone           VARCHAR(30),
    full_name       VARCHAR(120) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            user_role NOT NULL DEFAULT 'client',
    plan            plan_type NOT NULL DEFAULT 'free',
    plan_status     plan_status NOT NULL DEFAULT 'active',
    plan_expires_at TIMESTAMPTZ,
    telegram_chat_id BIGINT,
    whatsapp_number VARCHAR(30),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    otp_code        VARCHAR(8),
    otp_expires_at  TIMESTAMPTZ,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email        ON users(email);
CREATE INDEX idx_users_telegram     ON users(telegram_chat_id) WHERE telegram_chat_id IS NOT NULL;
CREATE INDEX idx_users_plan         ON users(plan, plan_status);
CREATE INDEX idx_users_active       ON users(is_active) WHERE is_active = TRUE;

-- Tokens JWT révocables
CREATE TABLE auth_tokens (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,
    token_type  VARCHAR(20) NOT NULL DEFAULT 'refresh', -- refresh | access
    is_revoked  BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address  INET,
    user_agent  TEXT
);

CREATE INDEX idx_tokens_user    ON auth_tokens(user_id, is_revoked);
CREATE INDEX idx_tokens_hash    ON auth_tokens(token_hash);

-- ============================================================
-- 2. GÉOGRAPHIE : PAYS & CENTRES VISA
-- ============================================================

CREATE TABLE countries (
    id          SERIAL PRIMARY KEY,
    code        CHAR(2) NOT NULL UNIQUE,  -- ISO 3166-1 alpha-2
    name_fr     VARCHAR(80) NOT NULL,
    name_en     VARCHAR(80) NOT NULL,
    flag_emoji  VARCHAR(10),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE visa_centers (
    id              SERIAL PRIMARY KEY,
    platform        VARCHAR(30) NOT NULL CHECK (platform IN ('BLS', 'TLScontact', 'VFS')),
    country_id      INT NOT NULL REFERENCES countries(id),
    city            VARCHAR(80) NOT NULL,
    address         TEXT,
    url_booking     TEXT NOT NULL,           -- URL de réservation à scraper
    url_check       TEXT,                    -- URL de vérification de dispo
    check_interval  SMALLINT NOT NULL DEFAULT 5,  -- fréquence en minutes
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_checked_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_centers_platform ON visa_centers(platform, is_active);
CREATE INDEX idx_centers_country  ON visa_centers(country_id);

-- Types de visa par pays
CREATE TABLE visa_types (
    id          SERIAL PRIMARY KEY,
    country_id  INT NOT NULL REFERENCES countries(id),
    code        VARCHAR(30) NOT NULL,   -- ex: SCHENGEN, LONG_SEJOUR, TRAVAIL
    label_fr    VARCHAR(100) NOT NULL,
    duration    VARCHAR(50),            -- ex: "90 jours/180 jours"
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(country_id, code)
);

-- ============================================================
-- 3. DOSSIERS CLIENTS (visa_requests)
-- ============================================================

CREATE TYPE request_status AS ENUM (
    'draft',        -- brouillon
    'active',       -- surveillance activée
    'slot_found',   -- créneau détecté
    'booked',       -- rendez-vous pris
    'completed',    -- visa obtenu
    'cancelled',    -- annulé
    'expired'       -- date dépassée
);

CREATE TYPE priority_level AS ENUM ('low', 'normal', 'high', 'urgent');

CREATE TABLE visa_requests (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    center_id       INT NOT NULL REFERENCES visa_centers(id),
    visa_type_id    INT REFERENCES visa_types(id),
    status          request_status NOT NULL DEFAULT 'draft',
    priority        priority_level NOT NULL DEFAULT 'normal',

    -- Préférences de créneau
    desired_date_from   DATE NOT NULL,
    desired_date_to     DATE,
    preferred_time_from TIME,
    preferred_time_to   TIME,
    num_applicants      SMALLINT NOT NULL DEFAULT 1,

    -- Infos dossier
    applicant_name  VARCHAR(120),
    passport_number VARCHAR(50),
    notes           TEXT,

    -- Tracking
    slot_found_at   TIMESTAMPTZ,
    booked_at       TIMESTAMPTZ,
    appointment_date DATE,
    appointment_time TIME,

    -- Audit
    created_by      UUID REFERENCES users(id),   -- agent ou user lui-même
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_requests_user     ON visa_requests(user_id, status);
CREATE INDEX idx_requests_center   ON visa_requests(center_id, status);
CREATE INDEX idx_requests_active   ON visa_requests(status, priority)
    WHERE status IN ('active', 'slot_found');
CREATE INDEX idx_requests_dates    ON visa_requests(desired_date_from, desired_date_to);

-- Documents uploadés
CREATE TABLE request_documents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id  UUID NOT NULL REFERENCES visa_requests(id) ON DELETE CASCADE,
    doc_type    VARCHAR(50) NOT NULL,   -- passeport, photo, justificatif...
    filename    VARCHAR(255) NOT NULL,
    file_path   TEXT NOT NULL,
    file_size   INT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 4. MONITORING — CRÉNEAUX DISPONIBLES
-- ============================================================

CREATE TYPE slot_status AS ENUM ('available', 'taken', 'expired');

CREATE TABLE appointment_slots (
    id              BIGSERIAL PRIMARY KEY,
    center_id       INT NOT NULL REFERENCES visa_centers(id),
    visa_type_id    INT REFERENCES visa_types(id),
    slot_date       DATE NOT NULL,
    slot_time       TIME,
    available_seats SMALLINT NOT NULL DEFAULT 1,
    status          slot_status NOT NULL DEFAULT 'available',
    raw_data        JSONB,               -- données brutes du scraping
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    taken_at        TIMESTAMPTZ,
    UNIQUE(center_id, slot_date, slot_time)
);

CREATE INDEX idx_slots_center_date ON appointment_slots(center_id, slot_date, status);
CREATE INDEX idx_slots_available   ON appointment_slots(status, slot_date)
    WHERE status = 'available';
CREATE INDEX idx_slots_date        ON appointment_slots(slot_date);

-- Logs de chaque vérification de monitoring
CREATE TABLE monitoring_logs (
    id              BIGSERIAL PRIMARY KEY,
    center_id       INT NOT NULL REFERENCES visa_centers(id),
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    duration_ms     INT,                  -- temps de réponse en ms
    slots_found     SMALLINT DEFAULT 0,
    slots_new       SMALLINT DEFAULT 0,   -- nouveaux créneaux cette passe
    http_status     SMALLINT,
    error_message   TEXT,
    raw_response    TEXT,                 -- pour debug
    success         BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_monlogs_center ON monitoring_logs(center_id, checked_at DESC);
CREATE INDEX idx_monlogs_errors ON monitoring_logs(success, checked_at DESC)
    WHERE success = FALSE;

-- ============================================================
-- 5. ALERTES & NOTIFICATIONS
-- ============================================================

CREATE TYPE alert_channel AS ENUM ('telegram', 'email', 'whatsapp', 'sms');
CREATE TYPE alert_status  AS ENUM ('pending', 'sent', 'failed', 'skipped');

CREATE TABLE alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    request_id      UUID REFERENCES visa_requests(id) ON DELETE SET NULL,
    slot_id         BIGINT REFERENCES appointment_slots(id) ON DELETE SET NULL,
    channel         alert_channel NOT NULL,
    status          alert_status NOT NULL DEFAULT 'pending',
    message         TEXT NOT NULL,
    sent_at         TIMESTAMPTZ,
    error_message   TEXT,
    retry_count     SMALLINT NOT NULL DEFAULT 0,
    max_retries     SMALLINT NOT NULL DEFAULT 3,
    scheduled_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alerts_user    ON alerts(user_id, created_at DESC);
CREATE INDEX idx_alerts_pending ON alerts(status, scheduled_at)
    WHERE status IN ('pending', 'failed');
CREATE INDEX idx_alerts_slot    ON alerts(slot_id);

-- Préférences de notification par utilisateur
CREATE TABLE notification_preferences (
    id              SERIAL PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    telegram_enabled  BOOLEAN NOT NULL DEFAULT TRUE,
    email_enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    whatsapp_enabled  BOOLEAN NOT NULL DEFAULT FALSE,
    sms_enabled       BOOLEAN NOT NULL DEFAULT FALSE,
    quiet_hours_start TIME,                     -- ex: 22:00
    quiet_hours_end   TIME,                     -- ex: 07:00
    max_alerts_per_day SMALLINT DEFAULT 20,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 6. ABONNEMENTS & FACTURATION
-- ============================================================

CREATE TYPE payment_method AS ENUM ('stripe', 'wave', 'orange_money', 'free_mobile', 'mtn', 'manual');
CREATE TYPE payment_status  AS ENUM ('pending', 'paid', 'failed', 'refunded', 'disputed');
CREATE TYPE invoice_status  AS ENUM ('draft', 'sent', 'paid', 'overdue', 'cancelled');

CREATE TABLE subscriptions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan            plan_type NOT NULL,
    status          plan_status NOT NULL DEFAULT 'active',
    price_fcfa      INT NOT NULL,
    billing_period  VARCHAR(20) NOT NULL DEFAULT 'monthly',  -- monthly | yearly
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    cancelled_at    TIMESTAMPTZ,
    auto_renew      BOOLEAN NOT NULL DEFAULT TRUE,
    stripe_sub_id   VARCHAR(100),           -- ID Stripe si applicable
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_subs_user      ON subscriptions(user_id, status);
CREATE INDEX idx_subs_expiry    ON subscriptions(expires_at, auto_renew)
    WHERE status = 'active';

CREATE TABLE invoices (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id),
    subscription_id UUID REFERENCES subscriptions(id),
    invoice_number  VARCHAR(30) NOT NULL UNIQUE,  -- VT-2026-001234
    status          invoice_status NOT NULL DEFAULT 'draft',
    amount_fcfa     INT NOT NULL,
    tax_fcfa        INT NOT NULL DEFAULT 0,
    total_fcfa      INT NOT NULL,
    description     TEXT,
    due_date        DATE NOT NULL,
    paid_at         TIMESTAMPTZ,
    pdf_path        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_invoices_user   ON invoices(user_id, created_at DESC);
CREATE INDEX idx_invoices_status ON invoices(status, due_date);

CREATE TABLE payments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id      UUID NOT NULL REFERENCES invoices(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    method          payment_method NOT NULL,
    status          payment_status NOT NULL DEFAULT 'pending',
    amount_fcfa     INT NOT NULL,
    currency        CHAR(3) NOT NULL DEFAULT 'XOF',
    gateway_ref     VARCHAR(150),   -- référence côté Stripe / Wave / OM
    gateway_data    JSONB,          -- payload complet du webhook
    paid_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_payments_invoice ON payments(invoice_id);
CREATE INDEX idx_payments_gateway ON payments(gateway_ref) WHERE gateway_ref IS NOT NULL;

-- ============================================================
-- 7. LOGS D'ADMIN & AUDIT
-- ============================================================

CREATE TABLE admin_actions (
    id          BIGSERIAL PRIMARY KEY,
    admin_id    UUID NOT NULL REFERENCES users(id),
    action      VARCHAR(80) NOT NULL,    -- ex: 'user.ban', 'plan.upgrade'
    target_type VARCHAR(50),             -- ex: 'user', 'request'
    target_id   VARCHAR(100),
    details     JSONB,
    ip_address  INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_admin_actions_admin ON admin_actions(admin_id, created_at DESC);
CREATE INDEX idx_admin_actions_type  ON admin_actions(action, created_at DESC);

-- ============================================================
-- 8. DONNÉES INITIALES
-- ============================================================

INSERT INTO countries (code, name_fr, name_en, flag_emoji) VALUES
    ('FR', 'France', 'France', '🇫🇷'),
    ('ES', 'Espagne', 'Spain', '🇪🇸'),
    ('DE', 'Allemagne', 'Germany', '🇩🇪'),
    ('IT', 'Italie', 'Italy', '🇮🇹'),
    ('CA', 'Canada', 'Canada', '🇨🇦'),
    ('PT', 'Portugal', 'Portugal', '🇵🇹'),
    ('BE', 'Belgique', 'Belgium', '🇧🇪'),
    ('NL', 'Pays-Bas', 'Netherlands', '🇳🇱'),
    ('US', 'États-Unis', 'United States', '🇺🇸'),
    ('GB', 'Royaume-Uni', 'United Kingdom', '🇬🇧');

INSERT INTO visa_centers (platform, country_id, city, url_booking, check_interval) VALUES
    ('BLS', 1, 'Dakar',   'https://blsspainfrance.com/senegal', 5),
    ('BLS', 2, 'Dakar',   'https://blsspainsenegal.com', 5),
    ('TLS', 1, 'Dakar',   'https://fr.tlscontact.com/visa/SN/fr', 5),
    ('TLS', 1, 'Abidjan', 'https://fr.tlscontact.com/visa/CI/fr', 10),
    ('VFS', 5, 'Dakar',   'https://www.vfsglobal.ca/canada/senegal', 10),
    ('VFS', 3, 'Dakar',   'https://www.vfsglobal.com/germany/senegal', 10);

-- ============================================================
-- 9. FONCTIONS & TRIGGERS UTILITAIRES
-- ============================================================

-- Mise à jour auto de updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_requests_updated_at
    BEFORE UPDATE ON visa_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Génération automatique du numéro de facture
CREATE SEQUENCE invoice_seq START 1000;

CREATE OR REPLACE FUNCTION generate_invoice_number()
RETURNS TRIGGER AS $$
BEGIN
    NEW.invoice_number = 'VT-' || TO_CHAR(NOW(), 'YYYY') || '-' ||
                         LPAD(nextval('invoice_seq')::TEXT, 6, '0');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_invoice_number
    BEFORE INSERT ON invoices
    FOR EACH ROW EXECUTE FUNCTION generate_invoice_number();

-- Vue pratique : dossiers actifs avec info centre et user
CREATE VIEW v_active_requests AS
SELECT
    vr.id,
    vr.user_id,
    u.full_name      AS client_name,
    u.email          AS client_email,
    u.plan           AS client_plan,
    u.telegram_chat_id,
    vc.platform,
    vc.city          AS center_city,
    vc.url_booking,
    vc.check_interval,
    c.name_fr        AS country_name,
    c.flag_emoji,
    vt.label_fr      AS visa_type,
    vr.status,
    vr.priority,
    vr.desired_date_from,
    vr.desired_date_to,
    vr.num_applicants,
    vr.created_at
FROM visa_requests vr
JOIN users         u  ON u.id  = vr.user_id
JOIN visa_centers  vc ON vc.id = vr.center_id
JOIN countries     c  ON c.id  = vc.country_id
LEFT JOIN visa_types vt ON vt.id = vr.visa_type_id
WHERE vr.status = 'active'
  AND u.is_active = TRUE;

-- Vue stats admin
CREATE VIEW v_admin_stats AS
SELECT
    (SELECT COUNT(*) FROM users WHERE is_active = TRUE)                         AS total_users,
    (SELECT COUNT(*) FROM users WHERE plan = 'premium' AND plan_status='active') AS premium_users,
    (SELECT COUNT(*) FROM users WHERE plan = 'vip'     AND plan_status='active') AS vip_users,
    (SELECT COUNT(*) FROM visa_requests WHERE status = 'active')                AS active_requests,
    (SELECT COUNT(*) FROM appointment_slots WHERE status='available'
     AND slot_date >= CURRENT_DATE)                                             AS available_slots,
    (SELECT COUNT(*) FROM alerts WHERE DATE(created_at) = CURRENT_DATE)         AS alerts_today,
    (SELECT COALESCE(SUM(amount_fcfa),0) FROM payments
     WHERE status='paid' AND DATE_TRUNC('month',paid_at) = DATE_TRUNC('month',NOW())) AS mrr_fcfa;
