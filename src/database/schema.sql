-- =====================================================================
-- PSXpert Database Schema (PostgreSQL 14+)
-- High-performance relational schema for Pakistan Stock Exchange (PSX)
-- Market Data, Financial Fundamentals, News Sentiment & Disclosures
-- =====================================================================

-- 1. DATA SOURCES & PROVENANCE
CREATE TABLE IF NOT EXISTS data_sources (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL,
    source_type VARCHAR(50) NOT NULL,       -- 'REST_API', 'WEB_SCRAPE', 'EXCHANGE_PORTAL'
    base_url VARCHAR(255),
    retrieval_timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    records_ingested INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'SUCCESS',    -- 'SUCCESS', 'PARTIAL', 'FAILED'
    provenance_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. COMPANIES DIRECTORY
CREATE TABLE IF NOT EXISTS companies (
    symbol VARCHAR(20) PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    sector VARCHAR(150) NOT NULL,
    sector_category VARCHAR(100),
    isin VARCHAR(50),
    is_shariah BOOLEAN DEFAULT FALSE,
    is_kse100 BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(sector);
CREATE INDEX IF NOT EXISTS idx_companies_isin ON companies(isin);

-- 3. DAILY STOCK PRICES (OHLCV)
CREATE TABLE IF NOT EXISTS stock_prices (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    trading_date DATE NOT NULL,
    open NUMERIC(12, 4),
    high NUMERIC(12, 4),
    low NUMERIC(12, 4),
    close NUMERIC(12, 4) NOT NULL,
    volume BIGINT DEFAULT 0,
    market_cap NUMERIC(20, 2),
    source_id INTEGER REFERENCES data_sources(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_stock_prices_symbol_date UNIQUE (symbol, trading_date)
);

CREATE INDEX IF NOT EXISTS idx_stock_prices_symbol ON stock_prices(symbol);
CREATE INDEX IF NOT EXISTS idx_stock_prices_date ON stock_prices(trading_date);
CREATE INDEX IF NOT EXISTS idx_stock_prices_symbol_date ON stock_prices(symbol, trading_date DESC);

-- 4. MARKET INDICES (e.g. KSE-100)
CREATE TABLE IF NOT EXISTS market_indices (
    id SERIAL PRIMARY KEY,
    index_symbol VARCHAR(20) NOT NULL,
    trading_date DATE NOT NULL,
    open NUMERIC(12, 4),
    high NUMERIC(12, 4),
    low NUMERIC(12, 4),
    close NUMERIC(12, 4) NOT NULL,
    volume BIGINT DEFAULT 0,
    point_change NUMERIC(12, 4),
    pct_change NUMERIC(8, 4),
    source_id INTEGER REFERENCES data_sources(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_market_indices_symbol_date UNIQUE (index_symbol, trading_date)
);

CREATE INDEX IF NOT EXISTS idx_market_indices_sym_date ON market_indices(index_symbol, trading_date DESC);

-- 5. NEWS ARTICLES
CREATE TABLE IF NOT EXISTS news_articles (
    id BIGSERIAL PRIMARY KEY,
    headline TEXT NOT NULL,
    summary TEXT,
    article_text TEXT,
    publisher VARCHAR(100) NOT NULL,
    url TEXT UNIQUE NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,       -- Preserves publication timezone (UTC / Asia/Karachi)
    source_id INTEGER REFERENCES data_sources(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_news_articles_pub_at ON news_articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_articles_publisher ON news_articles(publisher);

-- 6. NEWS ENTITIES (Article-to-Company and Article-to-Sector links)
CREATE TABLE IF NOT EXISTS news_entities (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL,       -- 'COMPANY', 'SECTOR', 'INDEX', 'MACRO'
    entity_value VARCHAR(150) NOT NULL,     -- e.g. 'OGDC', 'COMMERCIAL BANKS', 'KSE100'
    confidence_score NUMERIC(4, 3) DEFAULT 1.000,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_news_entity UNIQUE (article_id, entity_type, entity_value)
);

CREATE INDEX IF NOT EXISTS idx_news_entities_value ON news_entities(entity_value);
CREATE INDEX IF NOT EXISTS idx_news_entities_article_id ON news_entities(article_id);

-- 7. COMPANY FINANCIALS (Annual & Quarterly Fundamentals)
-- Note: 'publication_date' preserves the real announcement date to prevent lookahead bias in backtests
CREATE TABLE IF NOT EXISTS company_financials (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    statement_type VARCHAR(50) NOT NULL,    -- 'ANNUAL', 'QUARTERLY'
    fiscal_year INTEGER NOT NULL,
    fiscal_period VARCHAR(20) NOT NULL,     -- 'FY', 'Q1', 'Q2', 'Q3', 'Q4'
    period_end_date DATE NOT NULL,          -- Accounting period closing date
    publication_date DATE,                  -- Actual disclosure date to exchange (prevents lookahead bias)
    metric_name VARCHAR(100) NOT NULL,      -- e.g. 'revenue_sales', 'net_profit_after_tax', 'eps_basic'
    metric_value NUMERIC(20, 4),
    unit VARCHAR(50) DEFAULT 'PKR_THOUSANDS',
    source_id INTEGER REFERENCES data_sources(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_company_financials UNIQUE (symbol, statement_type, fiscal_year, fiscal_period, metric_name)
);

CREATE INDEX IF NOT EXISTS idx_company_financials_sym ON company_financials(symbol);
CREATE INDEX IF NOT EXISTS idx_company_financials_lookup ON company_financials(symbol, statement_type, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_company_financials_pub_date ON company_financials(publication_date);

-- 8. NEWS SENTIMENT (Model scores & labels for AI analytics)
CREATE TABLE IF NOT EXISTS news_sentiment (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    model_name VARCHAR(100) NOT NULL,       -- e.g. 'finbert-psx', 'vader', 'gemini-1.5-flash'
    sentiment_score NUMERIC(6, 4) NOT NULL, -- Normalized polarity score (-1.0000 to +1.0000)
    sentiment_label VARCHAR(20) NOT NULL,   -- 'POSITIVE', 'NEGATIVE', 'NEUTRAL'
    confidence NUMERIC(4, 3),
    positive_score NUMERIC(6, 4),
    negative_score NUMERIC(6, 4),
    neutral_score NUMERIC(6, 4),
    evaluation_metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_news_sentiment UNIQUE (article_id, model_name)
);

CREATE INDEX IF NOT EXISTS idx_news_sentiment_label ON news_sentiment(sentiment_label);
CREATE INDEX IF NOT EXISTS idx_news_sentiment_score ON news_sentiment(sentiment_score);

-- 9. CORPORATE ANNOUNCEMENTS (Disclosures, AGMs, Reports)
CREATE TABLE IF NOT EXISTS corporate_announcements (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    posting_date DATE NOT NULL,
    category VARCHAR(100) NOT NULL,         -- 'Earnings Announcements', 'Dividends & Bonus Shares', 'Material Disclosures', 'Corporate Events'
    title TEXT NOT NULL,
    announcement_id VARCHAR(100),
    document_url TEXT,
    attachment_url TEXT,
    source_id INTEGER REFERENCES data_sources(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_corp_announcements UNIQUE (symbol, announcement_id)
);

CREATE INDEX IF NOT EXISTS idx_corp_ann_sym_date ON corporate_announcements(symbol, posting_date DESC);
CREATE INDEX IF NOT EXISTS idx_corp_ann_category ON corporate_announcements(category);

-- 10. CORPORATE PAYOUTS (Historical Dividends, Splits & Bonus Shares 2001-2026)
CREATE TABLE IF NOT EXISTS corporate_payouts (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    announcement_date DATE NOT NULL,
    fiscal_year INTEGER NOT NULL,
    payout_type VARCHAR(50) NOT NULL,       -- 'dividend', 'split', 'bonus'
    dividend_per_share NUMERIC(10, 4),
    payout_percentage NUMERIC(8, 2),
    face_value NUMERIC(8, 2),
    source_id INTEGER REFERENCES data_sources(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_corp_payouts_sym_date ON corporate_payouts(symbol, announcement_date DESC);
