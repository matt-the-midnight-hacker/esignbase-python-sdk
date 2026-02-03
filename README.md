# esignbase-python-sdk
API Client for the [eSignBase](https://esignbase.com) API

The package provides a small, synchronous client for interacting with the eSignBase API.

Full REST API documentation is available at https://esignbase.com/en/api_documentation it also shows the format of the returned dictionary data.

### Classes

**GrantType** (Enum)

Defines the available OAuth2 grant types:

* CLIENT_CREDENTIALS: For server-to-server authentication
* AUTHORIZATION_CODE: For user-specific authentication


**Scope** (Enum)

Defines the available API permission scopes:

* ALL: Full access to all API endpoints
* READ: Read-only access
* CREATE_DOCUMENT: Permission to create documents
* DELETE: Permission to delete documents
* SANDBOX: Access to the sandbox environment, use this scope for testing

**OAuth2Client**

Main client class that stores authentication credentials and state.

Attributes:
```python
id (str) # Client ID from ESignBase
secret (str) # Client secret from ESignBase
grant_type (GrantType) # OAuth2 grant type to use
user_name (Optional[str]) # Username (required AUTHORIZATION_CODE)
password (Optional[str]) # Password (required AUTHORIZATION_CODE)
scope (list[Scope]) # List of requested API scopes
```
Retrieve your Client ID and Client Secret at https://app.esignbase.com/oauth2/client by creating an
OAuth2 Client Configuration.

**Recipient**

Represents a document recipient/signer.
`role_name` value is defined during template creation in the template editor.

Attributes:
```python
email (str) # Recipient's email address
first_name (str) # Recipient's first name
last_name (str) # Recipient's last name
role_name (str) # Role name (e.g., "Signer", "Viewer")
locale (str) # Locale code ("de", "en", "es")
```

**ESignBaseSDKError** (Exception)

Custom exception class for API-related errors.

### Functions

```python
def connect(client: OAuth2Client) -> None
```

Authenticates with the ESignBase API

Parameters:

    client: Configured OAuth2Client instance

Raises:

    ESignBaseSDKError: If authentication fails or validation fails

Example:
```python
client = OAuth2Client(
    id="your_client_id",
    secret="your_client_secret",
    grant_type=GrantType.CLIENT_CREDENTIALS,
    scope=[Scope.ALL],
)
connect(client)
```
---

```python
def get_templates(client: OAuth2Client) -> dict[str, Any]
```


Retrieves a list of available document templates.

Parameters:
```
client: Authenticated OAuth2Client instance
```

Returns Dictionary containing template data.

Raises:

    ESignBaseSDKError: If the API request fails

---

```python
def get_template(client: OAuth2Client, template_id: str) -> dict[str, Any]
```

Retrieves details of a specific template.

Parameters:

    client: Authenticated OAuth2Client instance
    template_id: Unique identifier of the template

Returns:
    Dictionary containing template details

Raises:
    ESignBaseSDKError: If the API request fails

---

```python
def get_documents(client: OAuth2Client, limit: int, offset: int) -> dict[str, Any]
```
Retrieves a paginated list of documents.

Parameters:

    client: Authenticated OAuth2Client instance
    limit: Maximum number of documents to return
    offset: Pagination offset

Returns:

    Dictionary containing document list and pagination info

Raises:

    ESignBaseSDKError: If the API request fails

---

```python
def get_document(client: OAuth2Client, document_id: str) -> dict[str, Any]
```

Retrieves details of a specific document.

Parameters:

    client: Authenticated OAuth2Client instance
    document_id: Unique identifier of the document

Returns:

    Dictionary containing document details

Raises:

    ESignBaseSDKError: If the API request fails

---

```python
def create_document(
    client: OAuth2Client,
    template_id: str,
    document_name: str,
    recipients: list[Recipient],
    user_defined_metadata: Optional[dict[str, str | int]] = None,
    expiration_date: Optional[datetime] = None
) -> dict[str, Any]
```

Creates a new document from a template.

Parameters:

    client: Authenticated OAuth2Client instance
    template_id: ID of the template to use
    document_name: Name for the new document
    recipients: List of Recipient objects
    user_defined_metadata: Optional metadata to attach to the document
    expiration_date: Optional expiration date for the document

Returns:

    Dictionary containing the created document details

Raises:

    ESignBaseSDKError: If the API request fails

Example:

```python
recipients = [
    Recipient(
        email="signer@example.com",
        first_name="John",
        last_name="Doe",
        role_name="signer",
        locale="de"
    )
]

document = create_document(
    client=client,
    template_id="template_123",
    document_name="Contract Agreement",
    recipients=recipients,
    user_defined_metadata={"contract_id": "CTR-2024-001"},
    expiration_date=datetime(2024, 12, 31)
)

```

---

```python
def delete_document(client: OAuth2Client, document_id: str) -> None
```

Deletes a specific document.

Parameters:

    client: Authenticated OAuth2Client instance
    document_id: Unique identifier of the document to delete

Raises:

    ESignBaseSDKError: If the API request fails

---

```python
def get_credits(client: OAuth2Client) -> dict[str, Any]
```

Retrieves credit balance information.

Parameters:

    client: Authenticated OAuth2Client instance

Returns:

    Dictionary containing credit balance data

Raises:

    ESignBaseSDKError: If the API request fails

Error Handling

All functions raise ESignBaseSDKError exceptions for API errors, network issues, or validation failures. Always wrap API calls in try-except blocks:

```python
try:
    templates = get_templates(client)
except ESignBaseSDKError as e:
    print(f"API Error: {e}")
```

Complete Example


```python

from datetime import datetime

# Setup client
client = OAuth2Client(
    id="your_client_id",
    secret="your_client_secret",
    grant_type=GrantType.CLIENT_CREDENTIALS,
    scope=[Scope.CREATE_DOCUMENT, Scope.READ]
)

# Authenticate
connect(client)

# Get available templates
templates = get_templates(client)

# Create a document
recipients = [
    Recipient(
        email="alice@example.com",
        first_name="Alice",
        last_name="Smith",
        role_name="Signer",
        locale="en"
    )
]
template_id = templates[0]["id"]

document = create_document(
    client=client,
    template_id=template_id,
    document_name="NDA Agreement",
    recipients=recipients
)

# Check document status
document_details = get_document(client, document["id"])

# Delete the document (if needed)
delete_document(client, document["id"])
```
