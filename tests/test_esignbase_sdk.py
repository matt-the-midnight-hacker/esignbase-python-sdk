from unittest import TestCase
from unittest.mock import Mock, patch

import esignbase_sdk


class TestEsignBaseSDK(TestCase):

    def test_client(self):
        client = esignbase_sdk.OAuth2Client(
            id="test_id",
            secret="test_secret",
            grant_type=esignbase_sdk.GrantType.CLIENT_CREDENTIALS,
            scope=[esignbase_sdk.Scope.ALL],
        )
        self.assertEqual(client.id, "test_id")
        self.assertEqual(client.secret, "test_secret")
        self.assertEqual(client.grant_type, esignbase_sdk.GrantType.CLIENT_CREDENTIALS)
        self.assertEqual(client.scope, [esignbase_sdk.Scope.ALL])

    def test_validate_requires_scope_and_credentials(self):
        # missing scope
        client = esignbase_sdk.OAuth2Client(
            id="id",
            secret="secret",
            grant_type=esignbase_sdk.GrantType.CLIENT_CREDENTIALS,
            scope=[],
        )
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk._validate(client)

        # missing id
        client = esignbase_sdk.OAuth2Client(
            id="",
            secret="secret",
            grant_type=esignbase_sdk.GrantType.CLIENT_CREDENTIALS,
            scope=[esignbase_sdk.Scope.READ],
        )
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk._validate(client)

        # missing secret
        client = esignbase_sdk.OAuth2Client(
            id="id",
            secret="",
            grant_type=esignbase_sdk.GrantType.CLIENT_CREDENTIALS,
            scope=[esignbase_sdk.Scope.READ],
        )
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk._validate(client)

    @patch("esignbase_sdk.requests.post")
    def test_connect_sets_access_token_on_success(self, post_mock: Mock):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"access_token": "abc123"}
        post_mock.return_value = mock_resp

        client = esignbase_sdk.OAuth2Client(
            id="id",
            secret="secret",
            grant_type=esignbase_sdk.GrantType.CLIENT_CREDENTIALS,
            scope=[esignbase_sdk.Scope.ALL],
        )
        esignbase_sdk.connect(client)
        self.assertEqual(client._access_token, "abc123")

    @patch("esignbase_sdk.requests.post")
    def test_connect_raises_on_http_error(self, post_mock: Mock):
        mock_resp = Mock()
        mock_resp.ok = False
        mock_resp.text = "bad"
        post_mock.return_value = mock_resp

        client = esignbase_sdk.OAuth2Client(
            id="id",
            secret="secret",
            grant_type=esignbase_sdk.GrantType.CLIENT_CREDENTIALS,
            scope=[esignbase_sdk.Scope.ALL],
        )
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk.connect(client)

    @patch("esignbase_sdk.requests.request")
    def test_get_templates_success_and_error(self, get_mock: Mock):
        # success
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = []
        get_mock.return_value = mock_resp

        client = esignbase_sdk.OAuth2Client(
            id="id",
            secret="secret",
            grant_type=esignbase_sdk.GrantType.CLIENT_CREDENTIALS,
            scope=[esignbase_sdk.Scope.ALL],
        )
        client._access_token = "tkn"
        res = esignbase_sdk.get_templates(client)
        self.assertEqual(res, [])

        # error
        mock_resp = Mock()
        mock_resp.ok = False
        mock_resp.text = "err"
        get_mock.return_value = mock_resp

        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk.get_templates(client)

    def test_validate_auth_code_requires_credentials(self):
        client = esignbase_sdk.OAuth2Client(
            id="id",
            secret="secret",
            grant_type=esignbase_sdk.GrantType.AUTHORIZATION_CODE,
            scope=[esignbase_sdk.Scope.READ],
        )
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk._validate(client)

    @patch("esignbase_sdk.requests.request")
    def test_create_document_includes_metadata_and_expiration(self, request_mock: Mock):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"id": "doc1"}
        request_mock.return_value = mock_resp

        client = esignbase_sdk.OAuth2Client(
            id="id",
            secret="secret",
            grant_type=esignbase_sdk.GrantType.CLIENT_CREDENTIALS,
            scope=[esignbase_sdk.Scope.ALL],
        )
        client._access_token = "tkn"

        recipients = [
            esignbase_sdk.Recipient(
                email="a@a.com", first_name="A", last_name="B", role_name="Signer", locale="en"
            )
        ]
        from datetime import datetime

        expiration = datetime(2025, 1, 1, 12, 0, 0)  # naive datetime should be treated as UTC
        res = esignbase_sdk.create_document(
            client,
            template_id="tpl",
            document_name="Doc",
            recipients=recipients,
            user_defined_metadata={"k": "v", "n": 1},
            expiration_date=expiration,
        )

        self.assertEqual(res, {"id": "doc1"})
        # inspect the json payload passed to requests.request
        _, kwargs = request_mock.call_args
        json_payload = kwargs.get("json")
        self.assertIsNotNone(json_payload)
        self.assertEqual(json_payload["user_defined_metadata"], {"k": "v", "n": 1})
        self.assertEqual(json_payload["name"], "Doc")
        self.assertEqual(json_payload["template_id"], "tpl")
        self.assertEqual(json_payload["recipients"][0]["email"], "a@a.com")
        self.assertTrue(json_payload["expiration_date"].endswith("+0000"))

    @patch("esignbase_sdk.requests.request")
    def test_download_document_streams_and_errors(self, request_mock: Mock):
        # success streaming
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.iter_content = Mock(return_value=[b"part1", b"part2"])
        request_mock.return_value = mock_resp

        client = esignbase_sdk.OAuth2Client(
            id="id",
            secret="secret",
            grant_type=esignbase_sdk.GrantType.CLIENT_CREDENTIALS,
            scope=[esignbase_sdk.Scope.ALL],
        )
        client._access_token = "tkn"
        chunks = list(esignbase_sdk.download_document(client, "docid"))
        self.assertEqual(b"".join(chunks), b"part1part2")

        # error case
        mock_resp = Mock()
        mock_resp.ok = False
        mock_resp.text = "err"
        request_mock.return_value = mock_resp
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            list(esignbase_sdk.download_document(client, "docid"))

    @patch("esignbase_sdk.connect")
    @patch("esignbase_sdk.requests.request")
    def test_api_request_reconnects_on_401(self, request_mock: Mock, connect_mock: Mock):
        # prepare responses: first is 401, second is successful
        resp1 = Mock()
        resp1.status_code = 401
        resp1.ok = False
        resp2 = Mock()
        resp2.status_code = 200
        resp2.ok = True
        resp2.json.return_value = {"ok": True}
        request_mock.side_effect = [resp1, resp2]

        def do_connect(c):
            c._access_token = "newtoken"

        connect_mock.side_effect = do_connect

        client = esignbase_sdk.OAuth2Client(
            id="id",
            secret="secret",
            grant_type=esignbase_sdk.GrantType.CLIENT_CREDENTIALS,
            scope=[esignbase_sdk.Scope.ALL],
        )
        client._access_token = "oldtoken"

        res = esignbase_sdk._api_request(client, "get", "api/something")
        self.assertIs(res, resp2)
        self.assertEqual(request_mock.call_count, 2)
        self.assertEqual(client._access_token, "newtoken")

    @patch("esignbase_sdk.requests.request")
    def test_get_template_documents_and_credits_error_and_success(self, request_mock: Mock):
        # success template
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"template": 1}
        request_mock.return_value = mock_resp

        client = esignbase_sdk.OAuth2Client(
            id="id",
            secret="secret",
            grant_type=esignbase_sdk.GrantType.CLIENT_CREDENTIALS,
            scope=[esignbase_sdk.Scope.ALL],
        )
        client._access_token = "tkn"
        self.assertEqual(esignbase_sdk.get_template(client, "t1"), {"template": 1})

        # error cases for get_template
        mock_resp = Mock()
        mock_resp.ok = False
        mock_resp.text = "err"
        mock_resp.status_code = 500
        request_mock.return_value = mock_resp
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk.get_template(client, "t1")

        # documents success
        mock_resp.ok = True
        mock_resp.json.return_value = {"docs": []}
        request_mock.return_value = mock_resp
        self.assertEqual(esignbase_sdk.get_documents(client, 10, 0), {"docs": []})

        # document error
        mock_resp.ok = False
        mock_resp.text = "err"
        request_mock.return_value = mock_resp
        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk.get_documents(client, 1, 0)

        # get_document success
        mock_resp.ok = True
        mock_resp.json.return_value = {"doc": 1}
        request_mock.return_value = mock_resp
        self.assertEqual(esignbase_sdk.get_document(client, "d1"), {"doc": 1})

        # delete_document success
        mock_resp.ok = True
        request_mock.return_value = mock_resp
        self.assertIsNone(esignbase_sdk.delete_document(client, "d1"))

        # get_credits success
        mock_resp.ok = True
        mock_resp.json.return_value = {"credits": 5}
        request_mock.return_value = mock_resp
        self.assertEqual(esignbase_sdk.get_credits(client), {"credits": 5})
