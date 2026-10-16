"""
PSXpert - SQLAlchemy Declarative Data Models
Defines relational models matching Phase 2 schema specifications.
"""

from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Numeric, Date,
    DateTime, Boolean, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from src.database.connection import Base


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(100), nullable=False)
    source_type = Column(String(50), nullable=False)
    base_url = Column(String(255), nullable=True)
    retrieval_timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    records_ingested = Column(Integer, default=0)
    status = Column(String(50), default="SUCCESS")
    provenance_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    stock_prices = relationship("StockPrice", back_populates="source")
    financials = relationship("CompanyFinancial", back_populates="source")


class Company(Base):
    __tablename__ = "companies"

    symbol = Column(String(20), primary_key=True)
    company_name = Column(String(255), nullable=False)
    sector = Column(String(150), nullable=False, index=True)
    sector_category = Column(String(100), nullable=True)
    isin = Column(String(50), nullable=True, index=True)
    is_shariah = Column(Boolean, default=False)
    is_kse100 = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    prices = relationship("StockPrice", back_populates="company", cascade="all, delete-orphan")
    financials = relationship("CompanyFinancial", back_populates="company", cascade="all, delete-orphan")
    announcements = relationship("CorporateAnnouncement", back_populates="company", cascade="all, delete-orphan")
    payouts = relationship("CorporatePayout", back_populates="company", cascade="all, delete-orphan")


class StockPrice(Base):
    __tablename__ = "stock_prices"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    symbol = Column(String(20), ForeignKey("companies.symbol", ondelete="CASCADE"), nullable=False, index=True)
    trading_date = Column(Date, nullable=False, index=True)
    open = Column(Numeric(12, 4), nullable=True)
    high = Column(Numeric(12, 4), nullable=True)
    low = Column(Numeric(12, 4), nullable=True)
    close = Column(Numeric(12, 4), nullable=False)
    volume = Column(BigInteger, default=0)
    market_cap = Column(Numeric(20, 2), nullable=True)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    company = relationship("Company", back_populates="prices")
    source = relationship("DataSource", back_populates="stock_prices")

    __table_args__ = (
        UniqueConstraint("symbol", "trading_date", name="uq_stock_prices_symbol_date"),
        Index("idx_prices_sym_date_desc", "symbol", "trading_date"),
    )


class MarketIndex(Base):
    __tablename__ = "market_indices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    index_symbol = Column(String(20), nullable=False, index=True)
    trading_date = Column(Date, nullable=False, index=True)
    open = Column(Numeric(12, 4), nullable=True)
    high = Column(Numeric(12, 4), nullable=True)
    low = Column(Numeric(12, 4), nullable=True)
    close = Column(Numeric(12, 4), nullable=False)
    volume = Column(BigInteger, default=0)
    point_change = Column(Numeric(12, 4), nullable=True)
    pct_change = Column(Numeric(8, 4), nullable=True)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("index_symbol", "trading_date", name="uq_market_indices_symbol_date"),
        Index("idx_market_indices_sym_date", "index_symbol", "trading_date"),
    )


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    headline = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    article_text = Column(Text, nullable=True)
    publisher = Column(String(100), nullable=False, index=True)
    url = Column(Text, unique=True, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    entities = relationship("NewsEntity", back_populates="article", cascade="all, delete-orphan")
    sentiment = relationship("NewsSentiment", back_populates="article", uselist=False, cascade="all, delete-orphan")


class NewsEntity(Base):
    __tablename__ = "news_entities"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    article_id = Column(BigInteger, ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)  # 'COMPANY', 'SECTOR', 'INDEX', 'MACRO'
    entity_value = Column(String(150), nullable=False, index=True)
    confidence_score = Column(Numeric(4, 3), default=1.000)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    article = relationship("NewsArticle", back_populates="entities")

    __table_args__ = (
        UniqueConstraint("article_id", "entity_type", "entity_value", name="uq_news_entity"),
    )


class CompanyFinancial(Base):
    __tablename__ = "company_financials"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    symbol = Column(String(20), ForeignKey("companies.symbol", ondelete="CASCADE"), nullable=False, index=True)
    statement_type = Column(String(50), nullable=False)  # 'ANNUAL', 'QUARTERLY'
    fiscal_year = Column(Integer, nullable=False)
    fiscal_period = Column(String(20), nullable=False)   # 'FY', 'Q1', 'Q2', 'Q3', 'Q4'
    period_end_date = Column(Date, nullable=False)       # Accounting closing date
    publication_date = Column(Date, nullable=True, index=True)  # Filing date (prevents lookahead bias)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Numeric(20, 4), nullable=True)
    unit = Column(String(50), default="PKR_THOUSANDS")
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    company = relationship("Company", back_populates="financials")
    source = relationship("DataSource", back_populates="financials")

    __table_args__ = (
        UniqueConstraint("symbol", "statement_type", "fiscal_year", "fiscal_period", "metric_name", name="uq_company_financials"),
        Index("idx_comp_fin_lookup", "symbol", "statement_type", "fiscal_year"),
    )


class NewsSentiment(Base):
    __tablename__ = "news_sentiment"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    article_id = Column(BigInteger, ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    sentiment_score = Column(Numeric(6, 4), nullable=False, index=True)  # Polarity (-1.0 to 1.0)
    sentiment_label = Column(String(20), nullable=False, index=True)     # 'POSITIVE', 'NEGATIVE', 'NEUTRAL'
    confidence = Column(Numeric(4, 3), nullable=True)
    positive_score = Column(Numeric(6, 4), nullable=True)
    negative_score = Column(Numeric(6, 4), nullable=True)
    neutral_score = Column(Numeric(6, 4), nullable=True)
    evaluation_metadata = Column(Text, nullable=True)  # JSON or text notes
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    article = relationship("NewsArticle", back_populates="sentiment")

    __table_args__ = (
        UniqueConstraint("article_id", "model_name", name="uq_news_sentiment"),
    )


class CorporateAnnouncement(Base):
    __tablename__ = "corporate_announcements"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    symbol = Column(String(20), ForeignKey("companies.symbol", ondelete="CASCADE"), nullable=False, index=True)
    posting_date = Column(Date, nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)
    title = Column(Text, nullable=False)
    announcement_id = Column(String(100), nullable=True)
    document_url = Column(Text, nullable=True)
    attachment_url = Column(Text, nullable=True)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    company = relationship("Company", back_populates="announcements")

    __table_args__ = (
        UniqueConstraint("symbol", "announcement_id", name="uq_corp_announcements"),
    )


class CorporatePayout(Base):
    __tablename__ = "corporate_payouts"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    symbol = Column(String(20), ForeignKey("companies.symbol", ondelete="CASCADE"), nullable=False, index=True)
    announcement_date = Column(Date, nullable=False, index=True)
    fiscal_year = Column(Integer, nullable=False)
    payout_type = Column(String(50), nullable=False)  # 'dividend', 'split', 'bonus'
    dividend_per_share = Column(Numeric(10, 4), nullable=True)
    payout_percentage = Column(Numeric(8, 2), nullable=True)
    face_value = Column(Numeric(8, 2), nullable=True)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    company = relationship("Company", back_populates="payouts")
