"""
URL feature engineering for the CyberShield AI phishing detector.

This module reproduces the 22 numeric features used to train the
``xgboost_url_detector.pkl`` model. The original training CSV contains the
raw URL, extracted domain metadata, and the model features; the feature logic
implemented here was inferred from those stored values.

Feature counting is intentionally performed on the stripped, original URL
text. URL component lengths are derived with :func:`urllib.parse.urlparse`.
Domain parsing is performed offline without DNS, WHOIS, or external APIs.
"""

from __future__ import annotations

import csv
import ipaddress
import math
from collections import Counter
from pathlib import Path
from typing import ClassVar, Iterable
from urllib.parse import ParseResult, urlparse

import pandas as pd


class FeatureExtractor:
    """
    Extract model-ready URL features for the XGBoost phishing detector.

    The public method :meth:`extract_features` returns a one-row
    :class:`pandas.DataFrame` with the exact feature names and order used
    during model training.
    """

    FEATURE_COLUMNS: ClassVar[list[str]] = [
        "url_len",
        "dom_len",
        "is_ip",
        "tld_len",
        "subdom_cnt",
        "letter_cnt",
        "digit_cnt",
        "special_cnt",
        "eq_cnt",
        "qm_cnt",
        "amp_cnt",
        "dot_cnt",
        "dash_cnt",
        "under_cnt",
        "letter_ratio",
        "digit_ratio",
        "spec_ratio",
        "is_https",
        "slash_cnt",
        "entropy",
        "path_len",
        "query_len",
    ]

    _FALLBACK_SUFFIXES: ClassVar[set[str]] = {
        "ac.id",
        "ac.in",
        "ac.jp",
        "ac.kr",
        "ac.uk",
        "app",
        "at",
        "be",
        "blog",
        "ca",
        "cn",
        "co",
        "co.in",
        "co.jp",
        "co.kr",
        "co.uk",
        "co.za",
        "com",
        "com.au",
        "com.br",
        "com.cn",
        "de",
        "dev",
        "edu",
        "edu.au",
        "edu.br",
        "edu.cn",
        "edu.in",
        "edu.mx",
        "edu.ph",
        "edu.tw",
        "eu",
        "fi",
        "fr",
        "go.jp",
        "go.kr",
        "gob.mx",
        "gov",
        "gov.au",
        "gov.br",
        "gov.cn",
        "gov.in",
        "gov.uk",
        "gr",
        "io",
        "it",
        "jp",
        "me",
        "net",
        "nhs.uk",
        "nl",
        "no",
        "or.jp",
        "or.kr",
        "org",
        "org.au",
        "org.br",
        "org.cn",
        "org.uk",
        "pl",
        "pt",
        "ru",
        "se",
        "shop",
        "sk",
    }
    _suffixes: ClassVar[tuple[str, ...] | None] = None

    def __init__(self) -> None:
        """Create a reusable, stateless feature extractor."""

    def extract_features(self, url: str) -> pd.DataFrame:
        """
        Extract the 22 training features from a URL.

        Parameters
        ----------
        url:
            URL text to analyze. Non-string values raise :class:`TypeError`.

        Returns
        -------
        pandas.DataFrame
            A one-row DataFrame whose columns exactly match the training
            feature order.
        """
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        raw_url = url.strip()
        parsed = self._parse_url(raw_url)
        host = self._hostname(parsed)
        domain, tld, is_ip = self._extract_domain_parts(host)

        url_len = len(raw_url)
        letter_cnt = sum(char.isalpha() for char in raw_url)
        digit_cnt = sum(char.isdigit() for char in raw_url)
        special_cnt = sum(not char.isalnum() for char in raw_url)

        row = {
            "url_len": url_len,
            "dom_len": len(domain),
            "is_ip": int(is_ip),
            "tld_len": len(tld),
            "subdom_cnt": self._subdomain_count(host, domain, is_ip),
            "letter_cnt": letter_cnt,
            "digit_cnt": digit_cnt,
            "special_cnt": special_cnt,
            "eq_cnt": raw_url.count("="),
            "qm_cnt": raw_url.count("?"),
            "amp_cnt": raw_url.count("&"),
            "dot_cnt": raw_url.count("."),
            "dash_cnt": raw_url.count("-"),
            "under_cnt": raw_url.count("_"),
            "letter_ratio": self._safe_ratio(letter_cnt, url_len),
            "digit_ratio": self._safe_ratio(digit_cnt, url_len),
            "spec_ratio": self._safe_ratio(special_cnt, url_len),
            "is_https": int(parsed.scheme.lower() == "https"),
            "slash_cnt": raw_url.count("/"),
            "entropy": self._shannon_entropy(raw_url),
            "path_len": len(parsed.path),
            "query_len": len(parsed.query),
        }

        return pd.DataFrame([[row[column] for column in self.FEATURE_COLUMNS]],
                            columns=self.FEATURE_COLUMNS)

    @classmethod
    def _parse_url(cls, url: str) -> ParseResult:
        """
        Parse a URL while also supporting scheme-less hostnames.

        ``urlparse`` treats ``example.com/path`` as a path. For production
        requests without a scheme, a network-path parse recovers the hostname
        while keeping all character-count features based on the original text.
        """
        parsed = urlparse(url)
        if parsed.scheme or parsed.netloc or not url:
            return parsed

        scheme_less = urlparse(f"//{url}")
        if scheme_less.netloc:
            return scheme_less
        return parsed

    @staticmethod
    def _hostname(parsed: ParseResult) -> str:
        """
        Return a normalized hostname from a parsed URL.

        Malformed netloc values can cause ``ParseResult.hostname`` to raise a
        ``ValueError``. In those cases the raw netloc is cleaned conservatively.
        """
        try:
            hostname = parsed.hostname or ""
        except ValueError:
            hostname = parsed.netloc.rsplit("@", maxsplit=1)[-1]
            hostname = hostname.rsplit(":", maxsplit=1)[0]

        return hostname.strip().strip("[]").rstrip(".").lower()

    @classmethod
    def _extract_domain_parts(cls, host: str) -> tuple[str, str, bool]:
        """
        Extract registrable domain, public suffix, and IP status.

        The training data follows public-suffix behavior. To stay offline and
        reproducible, the extractor loads suffixes observed in the bundled
        training CSV when available and otherwise falls back to common suffixes.
        Unknown suffixes intentionally produce an empty TLD, matching
        tldextract-style behavior for unrecognized malformed hosts.
        """
        if not host:
            return "", "", False

        is_ip = cls._is_ip_address(host)
        if is_ip:
            return host, "", True

        labels = [label for label in host.split(".") if label]
        if not labels:
            return "", "", False

        suffix = cls._match_public_suffix(host)
        if not suffix:
            return labels[-1], "", False

        suffix_label_count = len(suffix.split("."))
        if len(labels) <= suffix_label_count:
            return host, suffix, False

        domain = ".".join(labels[-(suffix_label_count + 1):])
        return domain, suffix, False

    @staticmethod
    def _is_ip_address(host: str) -> bool:
        """
        Return whether a hostname is an IPv4 or IPv6 address.

        Ports and IPv6 brackets are removed before this method is called.
        """
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return False
        return True

    @classmethod
    def _subdomain_count(cls, host: str, domain: str, is_ip: bool) -> int:
        """
        Count hostname labels before the registrable domain.

        The count includes ``www`` because the training CSV counted
        ``www.rmit.edu.au`` as one subdomain over ``rmit.edu.au``.
        """
        if not host or not domain or is_ip:
            return 0

        host_labels = [label for label in host.split(".") if label]
        domain_labels = [label for label in domain.split(".") if label]
        return max(0, len(host_labels) - len(domain_labels))

    @classmethod
    def _match_public_suffix(cls, host: str) -> str:
        """Return the longest known public suffix for a hostname."""
        for suffix in cls._public_suffixes():
            if host == suffix or host.endswith(f".{suffix}"):
                return suffix
        return ""

    @classmethod
    def _public_suffixes(cls) -> tuple[str, ...]:
        """
        Return public suffixes ordered for longest-match lookup.

        The CSV-derived list lets this module reproduce the original training
        feature values without network access or third-party suffix services.
        """
        if cls._suffixes is None:
            suffixes = set(cls._FALLBACK_SUFFIXES)
            suffixes.update(cls._load_training_suffixes())
            cls._suffixes = tuple(
                sorted(suffixes, key=lambda value: (-value.count("."),
                                                   -len(value), value))
            )
        return cls._suffixes

    @staticmethod
    def _load_training_suffixes() -> set[str]:
        """Load suffix values from the bundled training dataset if present."""
        candidates = (
            Path(__file__).resolve().parents[1]
            / "datasets"
            / "raw"
            / "Dataset___URL!.csv",
            Path(__file__).resolve().parents[1]
            / "dataset"
            / "Dataset___URL!.csv",
        )

        suffixes: set[str] = set()
        for dataset_path in candidates:
            if not dataset_path.is_file():
                continue
            try:
                suffixes.update(FeatureExtractor._read_suffixes(dataset_path))
            except (OSError, csv.Error, UnicodeDecodeError):
                continue
            if suffixes:
                break
        return suffixes

    @staticmethod
    def _read_suffixes(dataset_path: Path) -> Iterable[str]:
        """Yield non-empty TLD values from a training CSV."""
        with dataset_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                suffix = (row.get("tld") or "").strip().lower()
                if suffix:
                    yield suffix

    @staticmethod
    def _safe_ratio(count: int, total: int) -> float:
        """Return ``count / total`` while avoiding division by zero."""
        if total == 0:
            return 0.0
        return count / total

    @staticmethod
    def _shannon_entropy(value: str) -> float:
        """
        Compute Shannon entropy over characters in a string.

        The implementation matches the training values by using base-2
        logarithms over the original stripped URL text.
        """
        if not value:
            return 0.0

        length = len(value)
        counts = Counter(value)
        return -sum(
            (frequency / length) * math.log2(frequency / length)
            for frequency in counts.values()
        )
