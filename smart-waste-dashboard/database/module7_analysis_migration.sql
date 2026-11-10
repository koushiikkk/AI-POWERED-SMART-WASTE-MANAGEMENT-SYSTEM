-- ============================================================
-- Smart Waste Management Dashboard — Module 7 Migration
-- AI Image Analysis — schema updates for waste_reports
-- Executed: 2026-08-13
-- ============================================================

USE smart_waste_db;

-- ============================================================
-- 1. Update analysis_status CHECK constraint to include 'processing'
-- ============================================================

ALTER TABLE waste_reports
    DROP CHECK chk_analysis_status_valid;

ALTER TABLE waste_reports
    ADD CONSTRAINT chk_analysis_status_valid CHECK (
        analysis_status IN ('pending_analysis', 'processing', 'analyzed', 'failed')
    );

-- ============================================================
-- 2. Add AI provider metadata columns
-- ============================================================
-- analysis_provider: which AI service provided the analysis
-- analysis_model: specific model identifier used
-- analyzed_at: timestamp of when analysis completed

ALTER TABLE waste_reports
    ADD COLUMN analysis_provider VARCHAR(100) NULL,
    ADD COLUMN analysis_model VARCHAR(100) NULL,
    ADD COLUMN analyzed_at TIMESTAMP NULL;
