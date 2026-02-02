from base64 import b64encode
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Final, Optional

import requests

BASE_URL: Final[str] = "https://app.esignbase.com/api/"


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
    _access_token: Optional[str] = None
    scope: list[Scope] = field(default_factory=list[Scope])


@dataclass(slots=True)
class Recipient:
    email: str
    first_name: str
    last_name: str
    role_name: str
    locale: str


class ESignBaseSDKError(Exception):
    pass


def _validate(client: "OAuth2Client"):
    if not client.scope:
        raise ESignBaseSDKError("At least one scope must be provided")
    if not client.id:
        raise ESignBaseSDKError("Client ID is required")
    if not client.secret:
        raise ESignBaseSDKError("Client secret is required")
    if client.grant_type == GrantType.AUTHORIZATION_CODE:
        raise ESignBaseSDKError(
            "Username and password are required for authorization code grant type"
        )


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
        raise ESignBaseSDKError(f"Failed to connect to ESignBase API: {response.text}")
    client._access_token = response.json().get("access_token")


def get_templates(client: OAuth2Client) -> dict[str, Any]:
    response = requests.get(
        url=f"{BASE_URL}api/templates",
        headers={
            "Authorization": f"Bearer {client._access_token}",
        },
        timeout=15,
    )
    if not response.ok:
        raise ESignBaseSDKError(f"Failed to get templates: {response.text}")
    return response.json()


def get_template(client: OAuth2Client, template_id: str) -> dict[str, Any]:
    response = requests.get(
        url=f"{BASE_URL}api/template/{template_id}",
        headers={
            "Authorization": f"Bearer {client._access_token}",
        },
        timeout=15,
    )
    if not response.ok:
        raise ESignBaseSDKError(f"Failed to get template: {response.text}")
    return response.json()


def get_documents(client: OAuth2Client, limit: int, offset: int) -> dict[str, Any]:
    response = requests.get(
        url=f"{BASE_URL}api/documents",
        params={"limit": limit, "offset": offset},
        headers={
            "Authorization": f"Bearer {client._access_token}",
        },
        timeout=15,
    )
    if not response.ok:
        raise ESignBaseSDKError(f"Failed to get documents: {response.text}")
    return response.json()


def get_document(client: OAuth2Client, document_id: str) -> dict[str, Any]:
    response = requests.get(
        url=f"{BASE_URL}api/document/{document_id}",
        headers={
            "Authorization": f"Bearer {client._access_token}",
        },
        timeout=15,
    )
    if not response.ok:
        raise ESignBaseSDKError(f"Failed to get document: {response.text}")
    return response.json()


def create_document(
    client: OAuth2Client,
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
        request_data["expiration_date"] = expiration_date.strftime("%Y-%m-%dT%H:%M:%S%z")

    response = requests.post(
        url=f"{BASE_URL}api/document",
        json=request_data,
        headers={
            "Authorization": f"Bearer {client._access_token}",
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    if not response.ok:
        raise ESignBaseSDKError(f"Failed to create document: {response.text}")
    return response.json()


def delete_document(client: OAuth2Client, document_id: str) -> None:
    response = requests.delete(
        url=f"{BASE_URL}api/document/{document_id}",
        headers={
            "Authorization": f"Bearer {client._access_token}",
        },
        timeout=15,
    )
    if not response.ok:
        raise ESignBaseSDKError(f"Failed to delete document: {response.text}")
    return None


def get_credits(client: OAuth2Client) -> dict[str, Any]:
    response = requests.get(
        url=f"{BASE_URL}api/credits",
        headers={
            "Authorization": f"Bearer {client._access_token}",
        },
        timeout=15,
    )
    if not response.ok:
        raise ESignBaseSDKError(f"Failed to get credits: {response.text}")
    return response.json()
