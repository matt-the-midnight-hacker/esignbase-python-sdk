# pylint: disable=protected-access
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

import esignbase_sdk


def _make_client(**kwargs) -> esignbase_sdk.OAuth2Client:
    defaults = {"id": "test_id", "secret": "test_secret", "scope": [esignbase_sdk.Scope.ALL]}
    return esignbase_sdk.OAuth2Client(**{**defaults, **kwargs})


def _connected_client(**kwargs) -> esignbase_sdk.OAuth2Client:
    client = _make_client(**kwargs)
    client.access_token = "tkn"
    client._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=300)
    return client


class TestOAuth2Client(TestCase):

    def test_client_fields(self):
        client = _make_client()
        self.assertEqual(client.id, "test_id")
        self.assertEqual(client.secret, "test_secret")
        self.assertEqual(client.scope, [esignbase_sdk.Scope.ALL])

    def test_is_connected(self):
        client = _make_client()
        self.assertFalse(client.is_connected)
        client.access_token = "tkn"
        self.assertTrue(client.is_connected)

    def test_is_token_expired_when_no_expiry(self):
        client = _make_client()
        self.assertTrue(client.is_token_expired)

    def test_is_token_expired_when_past(self):
        client = _make_client()
        client._token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.assertTrue(client.is_token_expired)

    def test_is_token_expired_within_buffer(self):
        # within 30-second buffer window should be considered expired
        client = _make_client()
        client._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=20)
        self.assertTrue(client.is_token_expired)

    def test_is_token_not_expired(self):
        client = _make_client()
        client._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=60)
        self.assertFalse(client.is_token_expired)


class TestValidate(TestCase):

    def test_missing_scope(self):
        client = _make_client(scope=[])
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk._validate(client)

    def test_missing_id(self):
        client = _make_client(id="")
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk._validate(client)

    def test_missing_secret(self):
        client = _make_client(secret="")
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk._validate(client)

    def test_valid_client_passes(self):
        client = _make_client()
        esignbase_sdk._validate(client)  # should not raise


class TestConnect(TestCase):

    @patch("esignbase_sdk.requests.post")
    def test_sets_access_and_refresh_token(self, post_mock: Mock):
        post_mock.return_value = Mock(
            ok=True,
            json=Mock(
                return_value={
                    "access_token": "abc123",
                    "refresh_token": "ref456",
                    "expires_in": 300,
                }
            ),
        )
        client = _make_client()
        esignbase_sdk.connect(client)
        self.assertEqual(client.access_token, "abc123")
        self.assertEqual(client.refresh_token, "ref456")
        self.assertIsNotNone(client._token_expires_at)

    @patch("esignbase_sdk.requests.post")
    def test_clears_old_tokens_before_connecting(self, post_mock: Mock):
        post_mock.return_value = Mock(
            ok=True,
            json=Mock(return_value={"access_token": "new"}),
        )
        client = _make_client()
        client.access_token = "old"
        client.refresh_token = "old_ref"
        esignbase_sdk.connect(client)
        self.assertEqual(client.access_token, "new")

    @patch("esignbase_sdk.requests.post")
    def test_raises_on_http_error(self, post_mock: Mock):
        post_mock.return_value = Mock(ok=False, text="bad request")
        client = _make_client()
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk.connect(client)

    @patch("esignbase_sdk.requests.post")
    def test_token_expiry_is_set(self, post_mock: Mock):
        post_mock.return_value = Mock(
            ok=True,
            json=Mock(return_value={"access_token": "t", "expires_in": 300}),
        )
        client = _make_client()
        before = datetime.now(timezone.utc)
        esignbase_sdk.connect(client)
        after = datetime.now(timezone.utc)
        assert client._token_expires_at
        self.assertGreater(client._token_expires_at, before)
        self.assertLessEqual(client._token_expires_at, after + timedelta(seconds=300))


class TestRefresh(TestCase):

    @patch("esignbase_sdk.requests.post")
    def test_refresh_updates_tokens(self, post_mock: Mock):
        post_mock.return_value = Mock(
            ok=True,
            json=Mock(return_value={"access_token": "new_tkn", "refresh_token": "new_ref"}),
        )
        client = _make_client()
        client.access_token = "old_tkn"
        client.refresh_token = "old_ref"
        esignbase_sdk._refresh(client)
        self.assertEqual(client.access_token, "new_tkn")
        self.assertEqual(client.refresh_token, "new_ref")

    @patch("esignbase_sdk.connect")
    @patch("esignbase_sdk.requests.post")
    def test_refresh_falls_back_to_connect_on_failure(self, post_mock: Mock, connect_mock: Mock):
        post_mock.return_value = Mock(ok=False, text="invalid refresh token")
        client = _make_client()
        client.refresh_token = "bad_ref"
        esignbase_sdk._refresh(client)
        connect_mock.assert_called_once_with(client)

    @patch("esignbase_sdk.connect")
    def test_refresh_calls_connect_when_no_refresh_token(self, connect_mock: Mock):
        client = _make_client()
        client.refresh_token = None
        esignbase_sdk._refresh(client)
        connect_mock.assert_called_once_with(client)


class TestEnsureFresh(TestCase):

    @patch("esignbase_sdk._refresh")
    def test_refreshes_when_token_expired(self, refresh_mock: Mock):
        client = _make_client()
        client.access_token = "tkn"
        client._token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        esignbase_sdk._ensure_fresh(client)
        refresh_mock.assert_called_once_with(client)

    @patch("esignbase_sdk._refresh")
    def test_no_refresh_when_token_fresh(self, refresh_mock: Mock):
        client = _connected_client()
        esignbase_sdk._ensure_fresh(client)
        refresh_mock.assert_not_called()

    @patch("esignbase_sdk._refresh")
    def test_refreshes_when_not_connected(self, refresh_mock: Mock):
        client = _make_client()
        esignbase_sdk._ensure_fresh(client)
        refresh_mock.assert_called_once_with(client)


class TestApiRequest(TestCase):

    @patch("esignbase_sdk._ensure_fresh")
    @patch("esignbase_sdk.requests.request")
    def test_sets_authorization_header(self, request_mock: Mock, _ensure_fresh_mock: Mock):
        request_mock.return_value = Mock(ok=True)
        client = _connected_client()
        esignbase_sdk._api_request(client, "get", "api/something")
        _, kwargs = request_mock.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer tkn")

    @patch("esignbase_sdk._ensure_fresh")
    @patch("esignbase_sdk.requests.request")
    def test_calls_ensure_fresh(self, request_mock: Mock, ensure_fresh_mock: Mock):
        request_mock.return_value = Mock(ok=True)
        client = _connected_client()
        esignbase_sdk._api_request(client, "get", "api/something")
        ensure_fresh_mock.assert_called_once_with(client)


class TestGetTemplates(TestCase):

    @patch("esignbase_sdk.requests.request")
    def test_success(self, request_mock: Mock):
        request_mock.return_value = Mock(ok=True, json=Mock(return_value=[]))
        client = _connected_client()
        self.assertEqual(esignbase_sdk.get_templates(client), [])

    @patch("esignbase_sdk.requests.request")
    def test_error(self, request_mock: Mock):
        request_mock.return_value = Mock(ok=False, text="err")
        client = _connected_client()
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk.get_templates(client)


class TestGetTemplate(TestCase):

    @patch("esignbase_sdk.requests.request")
    def test_success(self, request_mock: Mock):
        request_mock.return_value = Mock(ok=True, json=Mock(return_value={"id": "t1"}))
        client = _connected_client()
        self.assertEqual(esignbase_sdk.get_template(client, "t1"), {"id": "t1"})

    @patch("esignbase_sdk.requests.request")
    def test_error(self, request_mock: Mock):
        request_mock.return_value = Mock(ok=False, text="err", status_code=404)
        client = _connected_client()
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk.get_template(client, "t1")


class TestGetDocuments(TestCase):

    @patch("esignbase_sdk.requests.request")
    def test_success(self, request_mock: Mock):
        request_mock.return_value = Mock(
            ok=True, json=Mock(return_value={"documents": [], "count": 0})
        )
        client = _connected_client()
        self.assertEqual(esignbase_sdk.get_documents(client, 10, 0), {"documents": [], "count": 0})

    @patch("esignbase_sdk.requests.request")
    def test_error(self, request_mock: Mock):
        request_mock.return_value = Mock(ok=False, text="err", status_code=500)
        client = _connected_client()
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk.get_documents(client, 10, 0)


class TestGetDocument(TestCase):

    @patch("esignbase_sdk.requests.request")
    def test_success(self, request_mock: Mock):
        request_mock.return_value = Mock(ok=True, json=Mock(return_value={"id": "d1"}))
        client = _connected_client()
        self.assertEqual(esignbase_sdk.get_document(client, "d1"), {"id": "d1"})

    @patch("esignbase_sdk.requests.request")
    def test_error(self, request_mock: Mock):
        request_mock.return_value = Mock(ok=False, text="err", status_code=404)
        client = _connected_client()
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk.get_document(client, "d1")


class TestCreateDocument(TestCase):

    def _recipients(self):
        return [
            esignbase_sdk.Recipient(
                email="a@a.com", first_name="A", last_name="B", role_name="signee_1", locale="en"
            )
        ]

    @patch("esignbase_sdk.requests.request")
    def test_success(self, request_mock: Mock):
        request_mock.return_value = Mock(ok=True, json=Mock(return_value={"document_id": "doc1"}))
        client = _connected_client()
        res = esignbase_sdk.create_document(
            client, template_id="tpl", document_name="Doc", recipients=self._recipients()
        )
        self.assertEqual(res, {"document_id": "doc1"})

    @patch("esignbase_sdk.requests.request")
    def test_includes_metadata_and_expiration(self, request_mock: Mock):
        request_mock.return_value = Mock(ok=True, json=Mock(return_value={"document_id": "doc1"}))
        client = _connected_client()
        expiration = datetime(2025, 1, 1, 12, 0, 0)  # naive — should be treated as UTC
        esignbase_sdk.create_document(
            client,
            template_id="tpl",
            document_name="Doc",
            recipients=self._recipients(),
            user_defined_metadata={"k": "v"},
            expiration_date=expiration,
        )
        _, kwargs = request_mock.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["user_defined_metadata"], {"k": "v"})
        self.assertTrue(payload["expiration_date"].endswith("+0000"))

    @patch("esignbase_sdk.requests.request")
    def test_error(self, request_mock: Mock):
        request_mock.return_value = Mock(ok=False, text="err", status_code=400)
        client = _connected_client()
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk.create_document(
                client, template_id="tpl", document_name="Doc", recipients=self._recipients()
            )


class TestDownloadDocument(TestCase):

    @patch("esignbase_sdk.requests.request")
    def test_streams_chunks(self, request_mock: Mock):
        request_mock.return_value = Mock(
            ok=True, iter_content=Mock(return_value=[b"part1", b"part2"])
        )
        client = _connected_client()
        chunks = list(esignbase_sdk.download_document(client, "docid"))
        self.assertEqual(b"".join(chunks), b"part1part2")

    @patch("esignbase_sdk.requests.request")
    def test_error(self, request_mock: Mock):
        request_mock.return_value = Mock(ok=False, text="err", status_code=404)
        client = _connected_client()
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            list(esignbase_sdk.download_document(client, "docid"))


class TestDeleteDocument(TestCase):

    @patch("esignbase_sdk.requests.request")
    def test_success(self, request_mock: Mock):
        request_mock.return_value = Mock(ok=True)
        client = _connected_client()
        self.assertIsNone(esignbase_sdk.delete_document(client, "d1"))

    @patch("esignbase_sdk.requests.request")
    def test_error(self, request_mock: Mock):
        request_mock.return_value = Mock(ok=False, text="err", status_code=404)
        client = _connected_client()
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk.delete_document(client, "d1")


class TestGetCredits(TestCase):

    @patch("esignbase_sdk.requests.request")
    def test_success(self, request_mock: Mock):
        request_mock.return_value = Mock(ok=True, json=Mock(return_value={"credits": 5}))
        client = _connected_client()
        self.assertEqual(esignbase_sdk.get_credits(client), {"credits": 5})

    @patch("esignbase_sdk.requests.request")
    def test_error(self, request_mock: Mock):
        request_mock.return_value = Mock(ok=False, text="err", status_code=500)
        client = _connected_client()
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk.get_credits(client)
