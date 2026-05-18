# pylint: disable=protected-access
from base64 import b64encode
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, Final, Optional, cast

import requests

BASE_URL: Final[str] = "https://app.esignbase.com/"
_TOKEN_EXPIRY_SECONDS: Final[int] = 300
_TOKEN_EXPIRY_BUFFER_SECONDS: Final[int] = 30

__all__ = (
    "GrantType",
    "Scope",
    "OAuth2Client",
    "Recipient",
    "ESignBaseSDKError",
    "connect",
    "get_templates",
    "get_template",
    "get_documents",
    "get_document",
    "create_document",
    "download_document",
    "delete_document",
    "get_credits",
)


class GrantType(StrEnum):
    CLIENT_CREDENTIALS = "client_credentials"


class Scope(StrEnum):
    ALL = "all"
    READ = "read"
    CREATE_DOCUMENT = "create_document"
    DELETE = "delete"
    SANDBOX = "sandbox"


@dataclass(slots=True)
class OAuth2Client:
    id: str
    secret: str
    scope: list[Scope] = field(default_factory=list)
    access_token: Optional[str] = field(default=None, repr=False)
    refresh_token: Optional[str] = field(default=None, repr=False)
    _token_expires_at: Optional[datetime] = field(default=None, repr=False)

    @property
    def is_connected(self) -> bool:
        """True when an access token exists."""
        return bool(self.access_token)

    @property
    def is_token_expired(self) -> bool:
        """True when the token is missing or about to expire within the buffer window."""
        if not self._token_expires_at:
            return True
        return datetime.now(timezone.utc) >= self._token_expires_at - timedelta(
            seconds=_TOKEN_EXPIRY_BUFFER_SECONDS
        )


@dataclass(slots=True)
class Recipient:
    email: str
    first_name: str
    last_name: str
    role_name: str
    locale: str


class ESignBaseSDKError(Exception):
    status_code: Optional[int] = None

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _validate(client: OAuth2Client):
    if not client.scope:
        raise ESignBaseSDKError("At least one scope must be provided")
    if not client.id:
        raise ESignBaseSDKError("Client ID is required")
    if not client.secret:
        raise ESignBaseSDKError("Client secret is required")


def _basic_auth_header(client: OAuth2Client) -> str:
    return b64encode(f"{client.id}:{client.secret}".encode()).decode()


def _apply_token_response(client: OAuth2Client, data: dict[str, Any]):
    """Update client token state from a token endpoint response."""
    client.access_token = data.get("access_token")
    client.refresh_token = data.get("refresh_token")
    expires_in = int(data.get("expires_in", _TOKEN_EXPIRY_SECONDS))
    client._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)


def _refresh(client: OAuth2Client):
    """Obtain a new access token using the refresh token."""
    if not client.refresh_token:
        connect(client)
        return

    response = requests.post(
        url=f"{BASE_URL}oauth2/token",
        data=(
            f"grant_type=refresh_token"
            f"&refresh_token={client.refresh_token}"
        ),
        headers={
            "Authorization": f"Basic {_basic_auth_header(client)}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=15,
    )
    if not response.ok:
        # Refresh token may have been revoked — fall back to a full connect
        connect(client)
        return

    _apply_token_response(client, response.json())


def _ensure_fresh(client: OAuth2Client):
    """Proactively refresh the token if it is expired or about to expire."""
    if not client.is_connected or client.is_token_expired:
        _refresh(client)


def _api_request(client: OAuth2Client, method: str, path: str, **kwargs) -> requests.Response:
    _ensure_fresh(client)
    headers = cast(dict[str, str], kwargs.pop("headers", {}) or {})
    headers["Authorization"] = f"Bearer {client.access_token}"
    kwargs["headers"] = headers
    url = f"{BASE_URL}{path.lstrip('/')}"
    return requests.request(method=method, url=url, timeout=15, **kwargs)


def connect(client: OAuth2Client):
    """Authenticate and obtain an access token using the client credentials grant."""
    client.access_token = None
    client.refresh_token = None
    client._token_expires_at = None

    _validate(client)

    response = requests.post(
        url=f"{BASE_URL}oauth2/token",
        data=f"grant_type=client_credentials&scope={' '.join(client.scope)}",
        headers={
            "Authorization": f"Basic {_basic_auth_header(client)}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=15,
    )
    if not response.ok:
        raise ESignBaseSDKError(
            f"Failed to connect to ESignBase API: {response.text}",
            status_code=response.status_code,
        )
    _apply_token_response(client, response.json())


def get_templates(client: OAuth2Client) -> list[dict[str, Any]]:
    response = _api_request(client, "get", "api/templates")
    if not response.ok:
        raise ESignBaseSDKError(f"Failed to get templates: {response.text}")
    return response.json()


def get_template(client: OAuth2Client, template_id: str) -> dict[str, Any]:
    response = _api_request(client, "get", f"api/template/{template_id}")
    if not response.ok:
        raise ESignBaseSDKError(
            f"Failed to get template: {response.text}", status_code=response.status_code
        )
    return response.json()


def get_documents(client: OAuth2Client, limit: int, offset: int) -> dict[str, Any]:
    response = _api_request(
        client, "get", "api/documents", params={"limit": limit, "offset": offset}
    )
    if not response.ok:
        raise ESignBaseSDKError(
            f"Failed to get documents: {response.text}",
            status_code=response.status_code,
        )
    return response.json()


def get_document(client: OAuth2Client, document_id: str) -> dict[str, Any]:
    response = _api_request(client, "get", f"api/document/{document_id}")
    if not response.ok:
        raise ESignBaseSDKError(
            f"Failed to get document: {response.text}", status_code=response.status_code
        )
    return response.json()


def create_document(  # pylint: disable=too-many-arguments
    client: OAuth2Client,
    *,
    template_id: str,
    document_name: str,
    recipients: list[Recipient],
    user_defined_metadata: Optional[dict[str, str]] = None,
    expiration_date: Optional[datetime] = None,
) -> dict[str, Any]:
    request_data: dict[str, Any] = {
        "name": document_name,
        "template_id": template_id,
        "recipients": [
            {
                "email": r.email,
                "first_name": r.first_name,
                "last_name": r.last_name,
                "role_name": r.role_name,
                "locale": r.locale,
            }
            for r in recipients
        ],
    }

    if user_defined_metadata:
        request_data["user_defined_metadata"] = user_defined_metadata

    if expiration_date:
        if expiration_date.tzinfo is None:
            expiration_date = expiration_date.replace(tzinfo=timezone.utc)
        request_data["expiration_date"] = expiration_date.strftime("%Y-%m-%dT%H:%M:%S%z")

    response = _api_request(
        client,
        "post",
        "api/document",
        json=request_data,
        headers={"Content-Type": "application/json"},
    )
    if not response.ok:
        raise ESignBaseSDKError(
            f"Failed to create document: {response.text}",
            status_code=response.status_code,
        )
    return response.json()


def download_document(client: OAuth2Client, document_id: str) -> Generator[bytes]:
    response = _api_request(client, "get", f"api/document/{document_id}/download", stream=True)
    if not response.ok:
        raise ESignBaseSDKError(
            f"Failed to download document: {response.text}",
            status_code=response.status_code,
        )
    yield from response.iter_content(chunk_size=8192)


def delete_document(client: OAuth2Client, document_id: str) -> None:
    response = _api_request(client, "delete", f"api/document/{document_id}")
    if not response.ok:
        raise ESignBaseSDKError(
            f"Failed to delete document: {response.text}",
            status_code=response.status_code,
        )


def get_credits(client: OAuth2Client) -> dict[str, Any]:
    response = _api_request(client, "get", "api/credits")
    if not response.ok:
        raise ESignBaseSDKError(
            f"Failed to get credits: {response.text}", status_code=response.status_code
        )
    return response.json()
