import json
import os
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import announce

class DiscordRoleTests(TestCase):
    def setUp(self):
        self.post = {
            "slug": "danganronpa-trigger-happy-havoc",
            "title": "Danganronpa",
            "description": "Review",
            "game": "Danganronpa",
            "reading_time": 12,
        }
        self.webhook = "https://discord.com/api/webhooks/test/url"
        self.url = "https://example.github.io/game-reviews"

    def payload(self, role_id):
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        with patch.dict(os.environ, {"DISCORD_ROLE_ID": role_id}, clear=False):
            with patch.object(announce.request, "urlopen", return_value=response) as mocked:
                announce.announce(self.post, self.webhook, self.url)
                return json.loads(mocked.call_args.args[0].data)

    def test_role_only(self):
        role = "123456789012345678"
        payload = self.payload(role)
        self.assertEqual(payload["content"], "<@&"+role+">")
        self.assertEqual(payload["allowed_mentions"], {"roles": [role]})
        self.assertNotIn("everyone", json.dumps(payload["allowed_mentions"]))

    def test_default_no_ping(self):
        payload = self.payload("")
        self.assertNotIn("content", payload)
        self.assertEqual(payload["allowed_mentions"], {"parse":[]})

    def test_invalid_role_id_rejected(self):
        with self.assertRaises(ValueError):
            self.payload("@the readers")
