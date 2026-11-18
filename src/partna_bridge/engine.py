from __future__ import annotations

from typing import Any

import httpx


class EngineError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class EngineClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", path, json=payload)

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("GET", path, params=params)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"X-API-Key": self._api_key, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=headers,
                    json=json,
                    params=params,
                )
        except httpx.HTTPError as error:
            raise EngineError(502, f"engine is unreachable: {error.__class__.__name__}") from error

        if response.status_code >= 400:
            raise EngineError(response.status_code, _detail(response))
        if not response.content:
            return {}
        return response.json()


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body, dict) and "detail" in body:
        return str(body["detail"])[:200]
    return str(body)[:200]
