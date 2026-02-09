-- =============================================
-- 광고를 잘 아는 사람들 — Supabase Schema v4
-- =============================================

-- 1. 사용자
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    position TEXT DEFAULT '',
    role TEXT DEFAULT 'STAFF',
    level INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 캠페인
CREATE TABLE IF NOT EXISTS campaigns (
    id BIGSERIAL PRIMARY KEY,
    campaign_name TEXT NOT NULL DEFAULT '',
    campaign_type TEXT DEFAULT 'smart_place',
    client_name TEXT DEFAULT '',
    place_url TEXT DEFAULT '',
    keywords TEXT DEFAULT '',
    daily_traffic INT DEFAULT 0,
    status TEXT DEFAULT 'active',
    memo TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. 순위 이력
CREATE TABLE IF NOT EXISTS rank_history (
    id BIGSERIAL PRIMARY KEY,
    keyword TEXT NOT NULL DEFAULT '',
    place_name TEXT DEFAULT '',
    rank INT DEFAULT 0,
    n1_score REAL DEFAULT 0,
    n2_score REAL DEFAULT 0,
    n3_score REAL DEFAULT 0,
    review_count INT DEFAULT 0,
    checked_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. 매출 (스프레드시트)
CREATE TABLE IF NOT EXISTS sales (
    id BIGSERIAL PRIMARY KEY,
    date TEXT DEFAULT '',
    client_name TEXT DEFAULT '',
    item TEXT DEFAULT '',
    amount INT DEFAULT 0,
    cost INT DEFAULT 0,
    profit INT DEFAULT 0,
    memo TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. 공지사항
CREATE TABLE IF NOT EXISTS notices (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    content TEXT DEFAULT '',
    author TEXT DEFAULT '',
    is_pinned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. 셀러 DB 캐시
CREATE TABLE IF NOT EXISTS seller_cache (
    id BIGSERIAL PRIMARY KEY,
    keyword TEXT DEFAULT '',
    name TEXT DEFAULT '',
    address TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    crawled_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- RLS 비활성화 (Service Key 사용하므로)
-- =============================================
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE rank_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales ENABLE ROW LEVEL SECURITY;
ALTER TABLE notices ENABLE ROW LEVEL SECURITY;
ALTER TABLE seller_cache ENABLE ROW LEVEL SECURITY;

-- 서비스 키로 모든 작업 허용
CREATE POLICY "service_all" ON users FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON campaigns FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON rank_history FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON sales FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON notices FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON seller_cache FOR ALL USING (true) WITH CHECK (true);

-- =============================================
-- 관리자 계정 (비밀번호: admin1234)
-- SHA256('admin1234') = ad66a0b77701a1d91d95ab8d9e12a3811c6028189d7523eac655533e8e1ecae1
-- =============================================
INSERT INTO users (user_id, password_hash, name, position, role, level)
VALUES ('admin', 'ad66a0b77701a1d91d95ab8d9e12a3811c6028189d7523eac655533e8e1ecae1', '대표', '대표이사', 'ADMIN', 5)
ON CONFLICT (user_id) DO NOTHING;
