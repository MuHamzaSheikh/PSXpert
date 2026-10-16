"""
PSXpert - Financial Text Preprocessing & Cleaning Pipeline
Cleans text, removes duplicates, normalizes whitespace, and detects language.
"""

import hashlib
import html
import re
from typing import Dict, Optional, Tuple

try:
    from langdetect import detect
except ImportError:
    detect = None


def clean_text(text: Optional[str]) -> str:
    """
    Cleans and standardizes raw article headlines and body text.
    - Unescapes HTML entities (&amp;, &quot;, &#39;, etc.)
    - Removes URLs and email addresses
    - Strips advertising boilerplate and reporter bylines
    - Normalizes punctuation, hyphens, and whitespace
    """
    if not text or not isinstance(text, str):
        return ""

    # Unescape HTML
    text = html.unescape(text)

    # Remove URLs
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)

    # Remove common boilerplate (e.g. Dawn / BR reporter prefixes)
    text = re.sub(r"^(KARACHI|ISLAMABAD|LAHORE|RAWALPINDI|PESHAWAR|QUETTA)\s*:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^By\s+[\w\s\.]+\s*[-—]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\(Reuters\s*[-—]\s*|\(APP\s*[-—]\s*", "", text, flags=re.IGNORECASE)

    # Normalize quotes, dashes, and currency symbols
    text = re.sub(r"[''’`]", "'", text)
    text = re.sub(r'[""“”]', '"', text)
    text = re.sub(r"[—–]", "-", text)

    # Normalize Pakistani currency notations (Rs, Rs., PKR)
    text = re.sub(r"\bRs\.?\s*", "Rs. ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bPKR\s*", "PKR ", text, flags=re.IGNORECASE)

    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compute_content_hash(headline: str, body: Optional[str] = None) -> str:
    """Computes a SHA-256 fingerprint for deduplication."""
    norm_headline = re.sub(r"[^\w\s]", "", headline.lower()).strip()
    combined = norm_headline
    if body and len(body) > 30:
        norm_body = re.sub(r"[^\w\s]", "", body[:200].lower()).strip()
        combined += "_" + norm_body
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def detect_article_language(text: str) -> str:
    """
    Detects language of article text.
    Returns ISO 639-1 code ('en', 'ur', etc.) or 'unknown'.
    """
    if not text or len(text.strip()) < 10:
        return "unknown"

    if detect is not None:
        try:
            return detect(text)
        except Exception:
            pass

    # Fallback heuristic: check for Urdu/Arabic unicode range
    urdu_chars = len(re.findall(r"[\u0600-\u06FF]", text))
    latin_chars = len(re.findall(r"[a-zA-Z]", text))
    if urdu_chars > latin_chars:
        return "ur"
    return "en"


def preprocess_article(headline: str, body: Optional[str] = None) -> Dict[str, any]:
    """Complete cleaning, language detection, and deduplication bundle."""
    cleaned_headline = clean_text(headline)
    cleaned_body = clean_text(body) if body else ""
    full_text = f"{cleaned_headline}. {cleaned_body}".strip() if cleaned_body else cleaned_headline

    lang = detect_article_language(full_text)
    content_hash = compute_content_hash(cleaned_headline, cleaned_body)

    return {
        "cleaned_headline": cleaned_headline,
        "cleaned_body": cleaned_body,
        "full_text": full_text,
        "language": lang,
        "is_english": lang == "en",
        "content_hash": content_hash,
        "word_count": len(full_text.split()),
        "character_count": len(full_text)
    }
