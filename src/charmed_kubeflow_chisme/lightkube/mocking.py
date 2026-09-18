# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tools for mocking with Lightkube."""

import httpx
from lightkube.core.exceptions import ApiError


class _FakeResponse:
    """Used to fake an httpx response during testing only."""

    def __init__(self, code):
        self.code = code
        self.name = ""

    def json(self):
        reason = ""
        if self.code == 409:
            reason = "AlreadyExists"
        return {
            "apiVersion": "v1",
            "code": self.code,
            "message": "broken",
            "reason": reason,
        }


class FakeApiError(ApiError):
    """Used to simulate an ApiError during testing."""

    def __init__(self, code=400):
        super().__init__(response=_FakeResponse(code))


def build_fake_unwrapped_http_status_error(code=404, content_type="text/plain"):
    """Builds a real, un-wrapped httpx.HTTPStatusError, as (un)mocked by lightkube.

    Lightkube only converts an `httpx.HTTPStatusError` into its own `ApiError` when the
    response's `Content-Type` header is `application/json` (see
    `lightkube.core.generic_client.transform_exception`). Kubernetes API servers return a
    non-JSON response (e.g. plain text) for a 404 against a completely unregistered API
    group/CRD, so in that case the raw `httpx.HTTPStatusError` is what actually propagates
    out of lightkube, not `ApiError`. This helper reproduces that exact, unwrapped exception
    for use in tests.
    """
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(
        status_code=code,
        headers={"Content-Type": content_type},
        content=b"404 page not found\n",
        request=request,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        return e
    raise AssertionError("code must be a 4xx/5xx status to build an HTTPStatusError")
