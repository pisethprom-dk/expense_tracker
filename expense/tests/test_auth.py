"""Tests for the token-auth endpoints in expense/auth_views.py."""
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .factories import make_user

LOGIN = "/api/auth/login/"
LOGOUT = "/api/auth/logout/"
ME = "/api/auth/me/"


class LoginTests(APITestCase):
    def setUp(self):
        self.user = make_user(username="alice", password="secret123")

    def test_login_returns_token(self):
        resp = self.client.post(
            LOGIN, {"username": "alice", "password": "secret123"}
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("token", resp.data)
        self.assertEqual(resp.data["username"], "alice")
        # token really exists in the DB
        self.assertTrue(Token.objects.filter(key=resp.data["token"]).exists())

    def test_login_wrong_password_401(self):
        resp = self.client.post(
            LOGIN, {"username": "alice", "password": "wrong"}
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_missing_fields_400(self):
        resp = self.client.post(LOGIN, {"username": "alice"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class MeAndLogoutTests(APITestCase):
    def setUp(self):
        self.user = make_user(username="bob", password="secret123")
        self.token = Token.objects.create(user=self.user)

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)

    def test_me_requires_auth(self):
        resp = self.client.get(ME)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_current_user(self):
        self._auth()
        resp = self.client.get(ME)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["username"], "bob")
        self.assertEqual(resp.data["user_id"], self.user.id)

    def test_logout_deletes_token(self):
        self._auth()
        resp = self.client.post(LOGOUT)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(user=self.user).exists())
        # the old token no longer works
        resp2 = self.client.get(ME)
        self.assertEqual(resp2.status_code, status.HTTP_401_UNAUTHORIZED)


class ProtectedAccessTests(APITestCase):
    def test_records_endpoint_requires_auth(self):
        resp = self.client.get("/api/records/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
