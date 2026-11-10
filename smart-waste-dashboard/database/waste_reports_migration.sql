-- ============================================================
-- Smart Waste Management Dashboard — Module 6 Migration
-- Citizen Waste Reporting — waste_reports table
-- ============================================================

USE smart_waste_db;

-- ============================================================
-- WASTE_REPORTS
-- ============================================================
-- Stores citizen-submitted waste reports with image + GPS.
-- analysis_status tracks processing state:
--   pending_analysis → analyzed | failed
-- severity/confidence/analysis_reason are NULL until
-- a real AI/image analysis pipeline populates them.
-- No FK to locations — citizen GPS coordinates are raw;
-- future modules can map to nearest location.

CREATE TABLE IF NOT EXISTS waste_reports (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    image_path      VARCHAR(500)    NOT NULL,
    latitude        DECIMAL(10,7)   NOT NULL,
    longitude       DECIMAL(10,7)   NOT NULL,
    analysis_status VARCHAR(30)     NOT NULL DEFAULT 'pending_analysis',
    severity        VARCHAR(20)     NULL,
    confidence      DECIMAL(5,2)    NULL,
    analysis_reason TEXT            NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- GPS coordinate range validation
    CONSTRAINT chk_latitude_range CHECK (latitude BETWEEN -90 AND 90),
    CONSTRAINT chk_longitude_range CHECK (longitude BETWEEN -180 AND 180),

    -- Analysis status lifecycle
    CONSTRAINT chk_analysis_status_valid CHECK (
        analysis_status IN ('pending_analysis', 'analyzed', 'failed')
    ),

    -- Severity values match existing waste status bands
    CONSTRAINT chk_severity_valid CHECK (
        severity IS NULL OR severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
    )
);
