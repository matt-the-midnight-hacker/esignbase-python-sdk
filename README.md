# eSignBase Python SDK

Official Python SDK for integrating **eIDAS-compliant electronic signatures** into your application using the [eSignBase](https://esignbase.com) REST API.

eSignBase provides GDPR-ready electronic signatures with EU-based infrastructure and flexible pay-as-you-go pricing — no subscriptions, no per-seat licenses.

## Why eSignBase?

- ✅ eIDAS-compliant electronic signatures
- ✅ GDPR-aligned EU data hosting
- ✅ No subscriptions — pay-as-you-go credits
- ✅ Automatic token refresh — no manual token management needed
- ✅ Lightweight, synchronous client with no heavy dependencies

## Installation

```bash
pip install esignbase-sdk
```

Requires Python 3.10 or higher.

## Quickstart

```python
import esignbase_sdk

# 1. Create and authenticate a client
client = esignbase_sdk.OAuth2Client(
    id="your_client_id",
    secret="your_client_secret",
    scope=[esignbase_sdk.Scope.ALL],
)
esignbase_sdk.connect(client)

# 2. List available templates
templates = esignbase_sdk.get_templates(client)

# 3. Send a document for signature
recipients = [
    esignbase_sdk.Recipient(
        email="alice@example.com",
        first_name="Alice",
        last_name="Smith",
        role_name="signee_1",  # must match a role defined in the template
        locale="en",
    )
]

document = esignbase_sdk.create_document(
    client=client,
    template_id=templates[0]["id"],
    document_name="NDA Agreement",
    recipients=recipients,
)

print(document)  # {"document_id": "...", "status": "DRAFT"}
```

Retrieve your Client ID and Client Secret at [app.esignbase.com/oauth2/client](https://app.esignbase.com/oauth2/client).

## Authentication

The SDK uses the OAuth2 **Client Credentials** grant. Call `connect()` once to authenticate — the SDK then manages token expiry and refresh automatically for all subsequent API calls.

```python
client = esignbase_sdk.OAuth2Client(
    id="your_client_id",
    secret="your_client_secret",
    scope=[esignbase_sdk.Scope.ALL],
)
esignbase_sdk.connect(client)
```

### Sandbox Mode

Use the `SANDBOX` scope to test without consuming credits. Sandbox mode uses templates created in your sandbox environment.

```python
client = esignbase_sdk.OAuth2Client(
    id="your_client_id",
    secret="your_client_secret",
    scope=[esignbase_sdk.Scope.ALL, esignbase_sdk.Scope.SANDBOX],
)
esignbase_sdk.connect(client)
```

## API Reference

### Scopes

| Scope | Description |
|---|---|
| `Scope.ALL` | Full access (read, create, delete). Does not include sandbox. |
| `Scope.READ` | Read documents and templates. |
| `Scope.CREATE_DOCUMENT` | Create and send documents for signature. |
| `Scope.DELETE` | Delete documents. |
| `Scope.SANDBOX` | Sandbox mode — no credits consumed. |

### `connect(client)`

Authenticates with the eSignBase API and stores the access token on the client. Raises `ESignBaseSDKError` if authentication fails.

### `get_templates(client)`

Returns a list of all available templates.

```python
templates = esignbase_sdk.get_templates(client)
# [{"id": "...", "filename": "contract.pdf", "form_role_names": ["signee_1"], ...}]
```

### `get_template(client, template_id)`

Returns details for a single template.

### `get_documents(client, limit, offset)`

Returns a paginated list of documents.

```python
result = esignbase_sdk.get_documents(client, limit=50, offset=0)
# {"documents": [...], "count": 120}
```

### `get_document(client, document_id)`

Returns details for a single document, including its current status.

### `create_document(client, *, template_id, document_name, recipients, user_defined_metadata=None, expiration_date=None)`

Creates a new document from a template and sends it to recipients.

`recipients` must include one `Recipient` per role defined in the template's `form_role_names`. `user_defined_metadata` is an optional `dict[str, str]` for attaching your own data (e.g. internal IDs) to the document.

```python
from datetime import datetime

document = esignbase_sdk.create_document(
    client=client,
    template_id="your_template_id",
    document_name="Employment Contract",
    recipients=[
        esignbase_sdk.Recipient(
            email="bob@example.com",
            first_name="Bob",
            last_name="Jones",
            role_name="signee_1",
            locale="de",
        )
    ],
    user_defined_metadata={"internal_id": "EMP-2024-042"},
    expiration_date=datetime(2025, 12, 31),
)
```

### `download_document(client, document_id)`

Streams a completed, signed PDF. Only available once the document status is `DIGITAL_SIGNATURE_CREATED` or `COMPLETED`.

```python
with open("signed_contract.pdf", "wb") as f:
    for chunk in esignbase_sdk.download_document(client, document["document_id"]):
        f.write(chunk)
```

### `delete_document(client, document_id)`

Deletes a document. Returns `None` on success.

### `get_credits(client)`

Returns the current credit balance.

```python
balance = esignbase_sdk.get_credits(client)
# {"credits": 42}
```

## Error Handling

All functions raise `ESignBaseSDKError` on failure. The exception includes a `status_code` attribute with the HTTP status code where applicable.

```python
try:
    document = esignbase_sdk.create_document(...)
except esignbase_sdk.ESignBaseSDKError as e:
    print(f"Error {e.status_code}: {e}")
```

## Document Statuses

| Status | Description |
|---|---|
| `DRAFT` | Created but not yet sent. |
| `SENT` | Sent to all recipients. |
| `PARTIALLY_SIGNED` | Signed by some recipients. |
| `COMPLETED` | Signing process complete. |
| `VOIDED` | Document expired or voided. |

Full status list available in the [API documentation](https://esignbase.com/en/api_documentation/).

## Further Reading

- [Full API Documentation](https://esignbase.com/en/api_documentation/)
- [Step-by-step REST API guide](https://esignbase.com/blog/rest-api-guide)
- [npm package (Node.js SDK)](https://www.npmjs.com/package/esignbase-sdk)

## License

MIT