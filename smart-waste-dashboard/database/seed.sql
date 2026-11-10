-- ============================================================
-- Smart Waste Management Dashboard — Seed Data
-- Module 2 — Created by Claude Opus 4.6 Thinking
-- ============================================================
-- Provides realistic sample data for dashboard testing.
-- Status bands (computed by backend, stored here for seed):
--   0–50%  capacity = LOW
--   51–75% capacity = MEDIUM
--   76–90% capacity = HIGH
--   91–100% capacity = CRITICAL
-- ============================================================

USE smart_waste_db;

-- ============================================================
-- LOCATIONS (10 rows)
-- ============================================================
-- Covers: multiple areas, multiple waste types,
-- and at least one location per status band.

INSERT INTO locations (name, area, waste_type, capacity, current_level, status) VALUES
-- LOW status (0–50%)
('MG Road Bin 4',           'MG Road',          'General',      100.00,  25.00, 'LOW'),
('Indiranagar Park Bin',    'Indiranagar',       'Organic',      150.00,  45.00, 'LOW'),
('Whitefield Tech Park',    'Whitefield',        'Recyclable',   200.00,  60.00, 'LOW'),

-- MEDIUM status (51–75%)
('Central Market',          'City Market',       'Organic',      120.00,  78.00, 'MEDIUM'),
('Koramangala Bin 7',       'Koramangala',       'General',      100.00,  65.00, 'MEDIUM'),

-- HIGH status (76–90%)
('University Gate',         'Malleshwaram',      'General',      100.00,  82.00, 'HIGH'),
('Jayanagar 4th Block',     'Jayanagar',         'Recyclable',   80.00,   68.00, 'HIGH'),

-- CRITICAL status (91–100%)
('KR Market South',         'City Market',       'Organic',      100.00,  95.00, 'CRITICAL'),
('Majestic Bus Stand',      'Majestic',          'General',      150.00, 142.00, 'CRITICAL'),
('Electronic City Phase 1', 'Electronic City',   'Hazardous',    60.00,   55.00, 'CRITICAL');


-- ============================================================
-- WASTE_RECORDS (20 rows)
-- ============================================================
-- Historical readings across various locations and times.

INSERT INTO waste_records (location_id, recorded_level, recorded_at) VALUES
-- MG Road Bin 4 (id=1) — trending low
(1,  10.00, '2026-08-10 08:00:00'),
(1,  18.00, '2026-08-11 08:00:00'),
(1,  25.00, '2026-08-12 08:00:00'),

-- Indiranagar Park Bin (id=2)
(2,  20.00, '2026-08-10 09:00:00'),
(2,  35.00, '2026-08-11 09:00:00'),
(2,  45.00, '2026-08-12 09:00:00'),

-- Central Market (id=4) — rising toward high
(4,  40.00, '2026-08-09 07:00:00'),
(4,  55.00, '2026-08-10 07:00:00'),
(4,  70.00, '2026-08-11 07:00:00'),
(4,  78.00, '2026-08-12 07:00:00'),

-- University Gate (id=6) — high
(6,  50.00, '2026-08-10 06:30:00'),
(6,  70.00, '2026-08-11 06:30:00'),
(6,  82.00, '2026-08-12 06:30:00'),

-- KR Market South (id=8) — critical, rising fast
(8,  60.00, '2026-08-09 06:00:00'),
(8,  75.00, '2026-08-10 06:00:00'),
(8,  88.00, '2026-08-11 06:00:00'),
(8,  95.00, '2026-08-12 06:00:00'),

-- Majestic Bus Stand (id=9) — critical
(9, 100.00, '2026-08-10 10:00:00'),
(9, 130.00, '2026-08-11 10:00:00'),
(9, 142.00, '2026-08-12 10:00:00');


-- ============================================================
-- COLLECTION_RECORDS (10 rows)
-- ============================================================
-- Covers all four lifecycle statuses.

INSERT INTO collection_records (location_id, status, assigned_to, created_at, completed_at) VALUES
-- Pending collections (3)
(8,  'pending',     NULL,               '2026-08-13 06:00:00', NULL),
(9,  'pending',     NULL,               '2026-08-13 06:15:00', NULL),
(6,  'pending',     NULL,               '2026-08-13 06:30:00', NULL),

-- Assigned collections (2)
(7,  'assigned',    'Ramesh Kumar',     '2026-08-12 14:00:00', NULL),
(10, 'assigned',    'Suresh Patil',     '2026-08-12 14:30:00', NULL),

-- In-progress collections (2)
(4,  'in_progress', 'Anita Sharma',     '2026-08-12 08:00:00', NULL),
(5,  'in_progress', 'Vikram Singh',     '2026-08-12 09:00:00', NULL),

-- Completed collections (3)
(1,  'completed',   'Priya Desai',      '2026-08-11 07:00:00', '2026-08-11 09:30:00'),
(2,  'completed',   'Rajesh Gupta',     '2026-08-11 08:00:00', '2026-08-11 11:00:00'),
(3,  'completed',   'Deepa Nair',       '2026-08-11 10:00:00', '2026-08-11 12:45:00');
