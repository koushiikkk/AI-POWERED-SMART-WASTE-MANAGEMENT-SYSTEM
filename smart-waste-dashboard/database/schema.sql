-- ============================================================
-- Smart Waste Management Dashboard — Database Schema
-- Module 2 — Created by Claude Opus 4.6 Thinking
-- ============================================================

-- Create database
CREATE DATABASE IF NOT EXISTS smart_waste_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE smart_waste_db;

-- ============================================================
-- 1. LOCATIONS
-- ============================================================
-- Core table: represents physical waste collection points.
-- status is stored as a derived value (LOW/MEDIUM/HIGH/CRITICAL)
-- computed by backend business logic based on current_level / capacity.

CREATE TABLE IF NOT EXISTS locations (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL,
    area            VARCHAR(100)    NOT NULL,
    waste_type      VARCHAR(50)     NOT NULL,
    capacity        DECIMAL(10,2)   NOT NULL,
    current_level   DECIMAL(10,2)   NOT NULL DEFAULT 0.00,
    status          VARCHAR(20)     NOT NULL DEFAULT 'LOW',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Capacity must be positive
    CONSTRAINT chk_capacity_positive CHECK (capacity > 0),

    -- Current level cannot be negative
    CONSTRAINT chk_current_level_non_negative CHECK (current_level >= 0),

    -- Status must be one of the defined bands
    CONSTRAINT chk_status_valid CHECK (status IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))
);

-- ============================================================
-- 2. WASTE_RECORDS
-- ============================================================
-- Historical log of waste level readings at each location.
-- Each row is a point-in-time snapshot of the recorded level.

CREATE TABLE IF NOT EXISTS waste_records (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    location_id     INT             NOT NULL,
    recorded_level  DECIMAL(10,2)   NOT NULL,
    recorded_at     TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key to locations
    CONSTRAINT fk_waste_records_location
        FOREIGN KEY (location_id) REFERENCES locations(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    -- Recorded level cannot be negative
    CONSTRAINT chk_recorded_level_non_negative CHECK (recorded_level >= 0)
);

-- ============================================================
-- 3. COLLECTION_RECORDS
-- ============================================================
-- Tracks the lifecycle of waste collection operations.
-- Lifecycle: pending → assigned → in_progress → completed

CREATE TABLE IF NOT EXISTS collection_records (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    location_id     INT             NOT NULL,
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending',
    assigned_to     VARCHAR(100)    NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP       NULL,

    -- Foreign key to locations
    CONSTRAINT fk_collection_records_location
        FOREIGN KEY (location_id) REFERENCES locations(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    -- Status must follow the defined lifecycle
    CONSTRAINT chk_collection_status_valid CHECK (status IN ('pending', 'assigned', 'in_progress', 'completed'))
);

-- ============================================================
-- USERS TABLE — DEFERRED
-- ============================================================
-- users table deferred because authentication is optional/P2.
-- Will only be created if login/role-based access is attempted
-- within the remaining exam time.
-- ============================================================
