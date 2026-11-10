-- Supabase schema for Smart Waste Management

-- Extensions
CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Profiles Table for RBAC
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('CITIZEN', 'STAFF', 'ADMIN')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Locations Table
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    area TEXT NOT NULL,
    waste_type TEXT NOT NULL,
    capacity NUMERIC(10,2) NOT NULL CHECK (capacity > 0),
    current_level NUMERIC(10,2) NOT NULL DEFAULT 0.00 CHECK (current_level >= 0),
    status TEXT NOT NULL DEFAULT 'LOW' CHECK (status IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Waste Records Table
CREATE TABLE IF NOT EXISTS waste_records (
    id SERIAL PRIMARY KEY,
    location_id INT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    recorded_level NUMERIC(10,2) NOT NULL CHECK (recorded_level >= 0),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Waste Reports Table (Citizen Portal)
CREATE TABLE IF NOT EXISTS waste_reports (
    id SERIAL PRIMARY KEY,
    image_path TEXT NOT NULL, -- Will store Supabase Storage path
    latitude NUMERIC(10,7) NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude NUMERIC(10,7) NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    analysis_status TEXT NOT NULL DEFAULT 'pending_analysis' CHECK (analysis_status IN ('pending_analysis', 'analyzed', 'failed')),
    severity TEXT CHECK (severity IS NULL OR severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    confidence NUMERIC(5,2),
    analysis_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reported_by_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL, -- Anonymous user id
    analysis_provider TEXT,
    analysis_model TEXT,
    analyzed_at TIMESTAMPTZ
);

-- 5. Collection Records Table
CREATE TABLE IF NOT EXISTS collection_records (
    id SERIAL PRIMARY KEY,
    location_id INT REFERENCES locations(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'assigned', 'in_progress', 'completed')),
    assigned_to TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    report_id INT REFERENCES waste_reports(id) ON DELETE SET NULL
);
