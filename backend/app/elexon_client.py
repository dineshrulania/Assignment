"""
Elexon BMRS Insights API client.

Responsibilities:
  - Construct and execute HTTP requests to the Elexon /stream endpoints.
  - Implement retry logic with exponential backoff.
  - Return raw list[dict] — zero processing at this layer.
  - Log every request and response (row count, elapsed time).

Verified facts (api_research.md):
  Base URL : https://data.elexon.co.uk/bmrs/api/v1
  Auth     : none required
  Format   : JSON array only on /stream endpoints
  FUELHH   : params settlementDateFrom, settlementDateTo, fuelType
  WINDFOR  : params publishDateTimeFrom, publishDateTimeTo
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class ElexonAPIError(Exception):
    """Raised when the Elexon API returns an error after all retries."""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ElexonClient:
    """
    Async HTTP client for the Elexon BMRS Insights API.

    Usage:
        async with ElexonClient() as client:
            raw = await client.fetch_fuelhh("2026-01-01", "2026-01-31")
    """

    BASE_URL = settings.elexon_base_url
    TIMEOUT = settings.elexon_timeout_seconds
    MAX_RETRIES = settings.elexon_max_retries
    BACKOFF_BASE = settings.elexon_retry_backoff_base

    # HTTP status codes that warrant a retry
    RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ElexonClient":
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(self.TIMEOUT),
            headers={"Accept": "application/json"},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()

    # ------------------------------------------------------------------ #
    # Public methods
    # ------------------------------------------------------------------ #

    async def fetch_fuelhh(
        self,
        settlement_date_from: str,
        settlement_date_to: str,
        fuel_type: str = "WIND",
    ) -> list[dict]:
        """
        Fetch half-hourly actual generation (FUELHH/stream).

        Parameters
        ----------
        settlement_date_from : YYYY-MM-DD  (inclusive)
        settlement_date_to   : YYYY-MM-DD  (inclusive)
        fuel_type            : Fuel type filter — "WIND" for this application.

        Returns
        -------
        list[dict]
            Raw JSON array from Elexon.  Each dict contains:
            dataset, publishTime, startTime, settlementDate,
            settlementPeriod, fuelType, generation.

        Verified fields: api_research.md §2.4
        """
        params: dict[str, str] = {
            "settlementDateFrom": settlement_date_from,
            "settlementDateTo": settlement_date_to,
            "fuelType": fuel_type,
        }
        return await self._get("/datasets/FUELHH/stream", params)

    async def fetch_windfor(
        self,
        publish_from: str,
        publish_to: str,
    ) -> list[dict]:
        """
        Fetch wind generation forecasts (WINDFOR/stream).

        Parameters
        ----------
        publish_from : ISO-8601 UTC (e.g. "2025-12-28T00:00:00Z")
        publish_to   : ISO-8601 UTC (e.g. "2026-02-01T00:00:00Z")

        Returns
        -------
        list[dict]
            Raw JSON array from Elexon.  Each dict contains:
            dataset, publishTime, startTime, generation.
            Note: NO settlementDate, settlementPeriod, or fuelType fields.

        Verified fields: api_research.md §3.4
        Important: filtering to January 2026 delivery dates is done in the
        processing layer, NOT here (no startTime filter available on this endpoint).
        """
        params: dict[str, str] = {
            "publishDateTimeFrom": publish_from,
            "publishDateTimeTo": publish_to,
        }
        return await self._get("/datasets/WINDFOR/stream", params)

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    async def _get(self, path: str, params: dict[str, str]) -> list[dict]:
        """
        Execute a GET request with retry and exponential backoff.

        Retries on:
          - Network/connection errors (httpx.RequestError)
          - Retryable HTTP status codes (429, 5xx)

        Does NOT retry on:
          - 4xx client errors (bad parameters)
        """
        if self._client is None:
            raise RuntimeError(
                "ElexonClient must be used as an async context manager."
            )

        last_exc: Exception | None = None
        url = f"{self.BASE_URL}{path}"

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                t0 = time.monotonic()
                logger.info(
                    "Elexon request attempt %d/%d  GET %s  params=%s",
                    attempt, self.MAX_RETRIES, path, params,
                )
                response = await self._client.get(path, params=params)
                elapsed = time.monotonic() - t0

                if response.status_code == 200:
                    data: list[dict] = response.json()
                    logger.info(
                        "Elexon response OK  GET %s  rows=%d  elapsed=%.2fs",
                        path, len(data), elapsed,
                    )
                    return data

                if response.status_code in self.RETRYABLE_STATUSES:
                    logger.warning(
                        "Elexon HTTP %d on attempt %d/%d  GET %s  — will retry",
                        response.status_code, attempt, self.MAX_RETRIES, path,
                    )
                    last_exc = ElexonAPIError(
                        f"HTTP {response.status_code} from Elexon",
                        status_code=response.status_code,
                    )
                else:
                    # Non-retryable 4xx — fail immediately
                    raise ElexonAPIError(
                        f"Elexon returned HTTP {response.status_code} for {path}: "
                        f"{response.text[:500]}",
                        status_code=response.status_code,
                    )

            except httpx.RequestError as exc:
                logger.warning(
                    "Elexon connection error on attempt %d/%d  GET %s: %s",
                    attempt, self.MAX_RETRIES, path, exc,
                )
                last_exc = ElexonAPIError(
                    f"Connection error reaching Elexon: {exc}"
                )

            # Exponential backoff before the next attempt
            if attempt < self.MAX_RETRIES:
                delay = self.BACKOFF_BASE * (2 ** (attempt - 1))
                logger.info("Waiting %.1fs before retry %d", delay, attempt + 1)
                await asyncio.sleep(delay)

        raise ElexonAPIError(
            f"Elexon request failed after {self.MAX_RETRIES} attempts for {path}."
        ) from last_exc


async def fetch_all_data() -> tuple[list[dict], list[dict]]:
    """
    Convenience function: fetch both FUELHH and WINDFOR in a single call.

    Returns
    -------
    (fuelhh_raw, windfor_raw)
        Both as raw list[dict] from Elexon.
    """
    s = get_settings()
    async with ElexonClient() as client:
        logger.info("Fetching FUELHH actuals (%s → %s, fuelType=%s)…",
                    s.actuals_date_from, s.actuals_date_to, s.actuals_fuel_type)
        fuelhh = await client.fetch_fuelhh(
            settlement_date_from=s.actuals_date_from,
            settlement_date_to=s.actuals_date_to,
            fuel_type=s.actuals_fuel_type,
        )
        logger.info("FUELHH fetch complete: %d raw rows", len(fuelhh))

        logger.info("Fetching WINDFOR forecasts (%s → %s)…",
                    s.forecasts_publish_from, s.forecasts_publish_to)
        windfor = await client.fetch_windfor(
            publish_from=s.forecasts_publish_from,
            publish_to=s.forecasts_publish_to,
        )
        logger.info("WINDFOR fetch complete: %d raw rows", len(windfor))

    return fuelhh, windfor
