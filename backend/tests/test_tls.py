"""Run with: backend/.venv/bin/python -m unittest discover -s backend/tests -p test_tls.py"""
import ssl
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.tls import verified_context


class TrustTests(unittest.TestCase):
    def test_verification_remains_enabled(self):
        context = verified_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    @patch.dict('os.environ', {}, clear=True)
    @patch('app.tls.sys.platform', 'darwin')
    @patch('app.tls.Path.is_file', return_value=True)
    @patch('app.tls.ssl.create_default_context')
    def test_missing_default_uses_macos_bundle(self, create, exists):
        context = MagicMock()
        context.get_ca_certs.return_value = []
        create.return_value = context
        self.assertIs(verified_context(), context)
        context.load_verify_locations.assert_called_once_with(cafile='/etc/ssl/cert.pem')

    @patch.dict('os.environ', {'SSL_CERT_FILE': '/custom/ca.pem'})
    @patch('app.tls.ssl.create_default_context')
    def test_explicit_trust_is_preserved(self, create):
        create.return_value.get_ca_certs.return_value = []
        verified_context()
        create.return_value.load_verify_locations.assert_not_called()
