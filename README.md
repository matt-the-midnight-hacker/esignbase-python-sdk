# esignbase-python-sdk
API Client for the [eSignBase](https://esignbase.com) API

The package provides a small, synchronous client for interacting with the eSignBase API.

Basic example

```python
from esignbase_sdk import (
    OAuth2Client,
    GrantType,
    Scope,
    Recipient,
    connect,
    get_templates,
    create_document,
    ESignBaseSDKError,
)

client = OAuth2Client(
    id="your-client-id",
    secret="your-client-secret",
    grant_type=GrantType.CLIENT_CREDENTIALS,
    scope=[Scope.READ, Scope.CREATE_DOCUMENT],
)

try:
    connect(client)
    templates = get_templates(client)
    print("Templates:", templates)

    recipient = Recipient(
        email="alice@example.com",
        first_name="Alice",
        last_name="Signer",
        role_name="signer",
        locale="en",
    )

    doc = create_document(
        client,
        template_id="template_id_here",
        document_name="My Document",
        recipients=[recipient],
    )
    print("Created document:", doc)
except ESignBaseSDKError as e:
    print("ESignBase error:", e)
```

Notes

- Authentication: call `connect(client)` to obtain and cache an access token on the provided `OAuth2Client` instance.
- Grant types: use `GrantType.CLIENT_CREDENTIALS` for machine-to-machine flows. For `GrantType.AUTHORIZATION_CODE` you must supply `user_name` and `password` on the `OAuth2Client` and the library will include them in the token request.
- Scopes: pass a list of `Scope` values to the `scope` parameter when creating `OAuth2Client`.
- Errors: API or validation errors raise `ESignBaseSDKError`.

Full REST API documentation is available at https://esignbase.com/en/api_documentation/
