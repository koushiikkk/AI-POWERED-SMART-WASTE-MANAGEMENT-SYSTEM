-- Row Level Security (RLS) policies for Smart Waste Management

-- Enable RLS on all tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE waste_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE waste_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE collection_records ENABLE ROW LEVEL SECURITY;

-- 1. Profiles Table Policies
-- Anyone can view profiles (needed for resolving names, or staff list)
CREATE POLICY "Profiles are viewable by everyone" ON profiles
    FOR SELECT USING (true);
    
-- Only the user can insert/update their own profile
CREATE POLICY "Users can insert their own profile" ON profiles
    FOR INSERT WITH CHECK (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON profiles
    FOR UPDATE USING (auth.uid() = id);

-- 2. Locations Table Policies
-- Locations are public (citizens need to see them to report near them, staff need to manage)
CREATE POLICY "Locations are viewable by everyone" ON locations
    FOR SELECT USING (true);

-- Only Staff and Admin can modify locations
CREATE POLICY "Staff/Admin can insert locations" ON locations
    FOR INSERT WITH CHECK (
        EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('STAFF', 'ADMIN'))
    );
CREATE POLICY "Staff/Admin can update locations" ON locations
    FOR UPDATE USING (
        EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('STAFF', 'ADMIN'))
    );
CREATE POLICY "Admin can delete locations" ON locations
    FOR DELETE USING (
        EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'ADMIN')
    );

-- 3. Waste Records Table Policies
CREATE POLICY "Waste records are viewable by everyone" ON waste_records
    FOR SELECT USING (true);
CREATE POLICY "Staff/Admin can manage waste_records" ON waste_records
    FOR ALL USING (
        EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('STAFF', 'ADMIN'))
    );

-- 4. Waste Reports Table Policies (Citizen Portal)
-- Citizens can view ONLY their own reports
-- Staff/Admin can view ALL reports
CREATE POLICY "Citizens view own reports, Staff/Admin view all" ON waste_reports
    FOR SELECT USING (
        auth.uid() = reported_by_user_id OR 
        EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('STAFF', 'ADMIN'))
    );

-- Citizens can create reports
CREATE POLICY "Citizens can insert reports" ON waste_reports
    FOR INSERT WITH CHECK (
        auth.uid() = reported_by_user_id OR reported_by_user_id IS NULL
    );

-- Staff/Admin can update reports (e.g. backend updating AI results bypassing RLS or service role, but good to have)
CREATE POLICY "Staff/Admin can update reports" ON waste_reports
    FOR UPDATE USING (
        EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('STAFF', 'ADMIN'))
    );

-- 5. Collection Records Table Policies
-- Only Staff/Admin can manage collection records
CREATE POLICY "Staff/Admin can view collection records" ON collection_records
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('STAFF', 'ADMIN'))
    );
CREATE POLICY "Staff/Admin can insert collection records" ON collection_records
    FOR INSERT WITH CHECK (
        EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('STAFF', 'ADMIN'))
    );
CREATE POLICY "Staff/Admin can update collection records" ON collection_records
    FOR UPDATE USING (
        EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('STAFF', 'ADMIN'))
    );
