from base64 import b64encode
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Final, Optional, cast

import requests

BASE_URL: Final[str] = "https://app.esignbase.com/"


class GrantType(StrEnum):
    CLIENT_CREDENTIALS = "client_credentials"
    AUTHORIZATION_CODE = "authorization_code"


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
    grant_type: GrantType
    user_name: Optional[str] = None
    password: Optional[str] = None
    access_token: Optional[str] = None
    scope: list[Scope] = field(default_factory=list[Scope])

    @property
    def is_connected(self) -> bool:
        """True when an access token exists."""
        return bool(self.access_token)


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


def _validate(client: "OAuth2Client"):
    if not client.scope:
        raise ESignBaseSDKError("At least one scope must be provided")
    if not client.id:
        raise ESignBaseSDKError("Client ID is required")
    if not client.secret:
        raise ESignBaseSDKError("Client secret is required")
    if client.grant_type == GrantType.AUTHORIZATION_CODE and (
        not client.user_name or not client.password
    ):
        raise ESignBaseSDKError(
            "Username and password are required for authorization code grant type"
        )


def _ensure_connected(client: OAuth2Client):
    if not client or not client.is_connected:
        raise ESignBaseSDKError("OAuth2Client is not connected. Call connect() first.")


def _api_request(client: OAuth2Client, method: str, path: str, retry: bool = True, **kwargs):
    _ensure_connected(client)
    headers = cast(dict[str, str], kwargs.pop("headers", {}) or {})
    # ensure Authorization header present
    headers.setdefault("Authorization", f"Bearer {client.access_token}")
    kwargs["headers"] = headers
    url = f"{BASE_URL}{path.lstrip('/')}"
    response = requests.request(method=method, url=url, timeout=15, **kwargs)
    # try to reconnect once on unauthorized
    if response.status_code == 401 and retry:
        try:
            connect(client)
        except Exception:
            # bubble original auth error if reconnect failed
            pass
        # update header with new token (connect may have set it)
        headers["Authorization"] = (
            f"Bearer {client.access_token}"
            if client.access_token
            else headers.get("Authorization", "")
        )
        kwargs["headers"] = headers
        response = requests.request(method=method, url=url, timeout=15, **kwargs)
    return response


def connect(client: OAuth2Client):

    _validate(client)
    auth_credentials = ""

    if client.grant_type == GrantType.AUTHORIZATION_CODE:
        if not client.user_name or not client.password:
            raise ESignBaseSDKError(
                "Username and password are required for authorization code grant type"
            )
        auth_credentials = f"username={client.user_name}&password={client.password}&"

    basic_auth_credentials = b64encode(f"{client.id}:{client.secret}".encode()).decode()

    response = requests.post(
        url=f"{BASE_URL}oauth2/token",
        data=f"{auth_credentials}grant_type={client.grant_type}&scope={' '.join(client.scope)}",
        headers={
            "Authorization": f"Basic {basic_auth_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=15,
    )
    if not response.ok:
        raise ESignBaseSDKError(
            f"Failed to connect to ESignBase API: {response.text}",
            status_code=response.status_code,
        )
    client.access_token = response.json().get("access_token")


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
    user_defined_metadata: Optional[dict[str, str | int]] = None,
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
        # ensure expiration_date is timezone-aware; assume UTC for naive datetimes
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
    response = _api_request(client, "get", f"api/document/download/{document_id}", stream=True)
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
