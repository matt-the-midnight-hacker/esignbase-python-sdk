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
    def test_connect_sets_access_token_on_success(self, post_mock):
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
    def test_connect_raises_on_http_error(self, post_mock):
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

    @patch("esignbase_sdk.requests.get")
    def test_get_templates_success_and_error(self, get_mock):
        # success
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"templates": []}
        get_mock.return_value = mock_resp

        client = esignbase_sdk.OAuth2Client(
            id="id",
            secret="secret",
            grant_type=esignbase_sdk.GrantType.CLIENT_CREDENTIALS,
            scope=[esignbase_sdk.Scope.ALL],
        )
        client._access_token = "tkn"
        res = esignbase_sdk.get_templates(client)
        self.assertIn("templates", res)

        # error
        mock_resp = Mock()
        mock_resp.ok = False
        mock_resp.text = "err"
        get_mock.return_value = mock_resp

        with self.assertRaises(esignbase_sdk.ESignBaseSDKError):
            esignbase_sdk.get_templates(client)
