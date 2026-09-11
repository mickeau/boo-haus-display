import json
import os
import re
import time
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import logging
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

try:
    from config import PROJECT_ROOT
except Exception:
    PROJECT_ROOT = Path.cwd()

logger = logging.getLogger(__name__)

NETWORK_DISABLED_ENV = "BOO_HAUS_OFFLINE"
DEFAULT_HEADERS = {
    "User-Agent": "BooHausDisplay/1.0 (+https://github.com/boo-haus-display)"
}
SECRET_QUERY_PARAMS = {
    "appid",
    "api_key",
    "apikey",
    "key",
    "token",
    "access_token",
}


def network_disabled():
    """Return True when tests or diagnostics have explicitly disabled live network calls."""
    return os.environ.get(NETWORK_DISABLED_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _redact_url(url):
    parts = urlsplit(str(url))
    if not parts.query:
        return str(url)

    redacted_query = urlencode([
        (key, "<redacted>" if key.lower() in SECRET_QUERY_PARAMS else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, redacted_query, parts.fragment))


def sanitize_request_error(error, secret_values=()):
    """Remove common API credential values from request error text."""
    message = str(error)

    for value in secret_values:
        if value:
            message = message.replace(str(value), "<redacted>")

    secret_param_pattern = "|".join(re.escape(param) for param in SECRET_QUERY_PARAMS)
    return re.sub(
        rf"\b({secret_param_pattern})=[^&\s)'\"]+",
        r"\1=<redacted>",
        message,
        flags=re.IGNORECASE,
    )


def http_get(url, *, params=None, headers=None, timeout=15, session=None, description=None, secret_values=()):
    """GET a URL with shared timeout, headers, and sanitized error logging."""
    if network_disabled():
        logger.info(f"Network disabled; skipping {description or _redact_url(url)}")
        return None

    client = session or requests
    request_headers = dict(DEFAULT_HEADERS)
    if headers:
        request_headers.update(headers)

    try:
        response = client.get(url, params=params, headers=request_headers, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        safe_url = _redact_url(getattr(getattr(e, "response", None), "url", None) or getattr(getattr(e, "request", None), "url", None) or url)
        safe_error = sanitize_request_error(e, secret_values=secret_values)
        logger.error(f"{description or 'HTTP request'} failed ({safe_url}): {safe_error}")
        return None


def http_get_json(url, **kwargs):
    response = http_get(url, **kwargs)
    if response is None:
        return None

    try:
        return response.json()
    except ValueError as e:
        logger.error(f"Invalid JSON from {_redact_url(response.url)}: {e}")
        return None


def http_get_text(url, **kwargs):
    response = http_get(url, **kwargs)
    return response.text if response is not None else None


class BaseFetcher(ABC):
    def __init__(self, cache_file: str, cache_expiry_minutes: int = 60):
        cache_path = Path(cache_file)
        self.cache_file = str(cache_path if cache_path.is_absolute() else PROJECT_ROOT / cache_path)
        self.cache_expiry_minutes = cache_expiry_minutes
        self._cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                if self._is_cache_valid(cache_data):
                    logger.info(f"Loaded valid cache from {self.cache_file}")
                else:
                    logger.info(f"Loaded stale cache from {self.cache_file}")
                return cache_data
            except json.JSONDecodeError:
                logger.warning(f"Corrupted cache file {self.cache_file}, creating new one.")
            except OSError as e:
                logger.error(f"Error loading cache from {self.cache_file}: {e}, creating new one.")
        logger.info(f"No valid cache found for {self.cache_file}, initializing empty cache.")
        return {"timestamp": None, "data": None}

    def _is_cache_valid(self, cache_data: dict) -> bool:
        if not isinstance(cache_data, dict):
            return False

        timestamp = cache_data.get("timestamp")
        if timestamp is None or cache_data.get("data") is None:
            return False

        try:
            cached_time = datetime.fromisoformat(str(timestamp))
        except ValueError:
            return False

        if cached_time.tzinfo is not None and cached_time.utcoffset() is not None:
            now = datetime.now(cached_time.tzinfo)
        else:
            now = datetime.now()

        return (now - cached_time) < timedelta(minutes=self.cache_expiry_minutes)

    def _save_cache(self, data):
        self._cache = {"timestamp": datetime.now().isoformat(), "data": data}
        try:
            tmp_file = self.cache_file + '.tmp'
            with open(tmp_file, 'w') as f:
                json.dump(self._cache, f, indent=2)
            os.replace(tmp_file, self.cache_file)
            logger.info(f"Cache saved to {self.cache_file}")
        except (OSError, TypeError) as e:
            logger.error(f"Error saving cache to {self.cache_file}: {e}")

    def _has_stale_cache(self):
        """Check if we have any cached data at all, even if expired."""
        return isinstance(self._cache, dict) and self._cache.get("data") is not None

    def fetch_data(self, force_refresh: bool = False):
        if not force_refresh and self._is_cache_valid(self._cache):
            logger.info(f"Returning cached data for {self.cache_file}")
            return self._cache["data"]

        if network_disabled():
            if self._has_stale_cache():
                logger.info(f"Network disabled; returning cached data for {self.cache_file}")
                return self._cache["data"]
            logger.info(f"Network disabled and no cache available for {self.cache_file}")
            return None

        try:
            data = self._fetch_data_from_source()
        except Exception as e:
            logger.error(f"Error fetching from source for {self.cache_file}: {e}")
            data = None

        if data is not None:
            self._save_cache(data)
            return data

        # Fresh fetch failed — fall back to stale cache if available
        if self._has_stale_cache():
            logger.warning(f"Using stale cache for {self.cache_file} (fetch failed)")
            return self._cache["data"]

        return data

    @abstractmethod
    def _fetch_data_from_source(self):
        """Abstract method to be implemented by subclasses to fetch data from its source."""
        pass
