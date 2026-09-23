"""PA-2 tests: Durable Encrypted Conversation Provenance.

Covers:
- Conversation CRUD
- Encrypted message storage (AES-256-GCM)
- Encryption acceptance: sentinel, wrong-key, tamper, AAD cross-conversation
- Key version retention
- Conversation↔Task provenance durability
- Cross-conversation isolation
- No plaintext in stored payload
"""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from runtime.kernel.conversation import (
    ConversationService, ConversationCrypto, KeyProvider,
    WrappedDEK, SCHEMA_VERSION, AES_KEY_SIZE, NONCE_SIZE,
)


class ConversationCryptoTests(unittest.TestCase):
    """Unit tests for the encryption layer."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data_dir = Path(self.tmp)
        self.kp = KeyProvider(self.data_dir)
        self.crypto = ConversationCrypto(self.kp)

    def test_kek_created_and_persisted(self):
        kek1 = self.kp.load_or_create()
        self.assertEqual(len(kek1), AES_KEY_SIZE)
        # Reload from disk
        kp2 = KeyProvider(self.data_dir)
        kek2 = kp2.load_or_create()
        self.assertEqual(kek1, kek2)

    def test_kek_file_permissions(self):
        self.kp.load_or_create()
        key_file = self.data_dir / 'conversation-kek.key'
        mode = os.stat(str(key_file)).st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_encrypt_decrypt_roundtrip(self):
        dek = self.crypto.generate_dek()
        plaintext = "BLAINE_SECRET_SENTINEL_test123"
        ct, nonce = self.crypto.encrypt(dek, plaintext, 'domain-1', 'conv-1', 'msg-1')
        self.assertNotEqual(ct, plaintext.encode())
        decrypted = self.crypto.decrypt(dek, ct, nonce, 'domain-1', 'conv-1', 'msg-1')
        self.assertEqual(decrypted, plaintext)

    def test_wrong_key_fails_closed(self):
        dek = self.crypto.generate_dek()
        wrong_dek = self.crypto.generate_dek()
        ct, nonce = self.crypto.encrypt(dek, "secret", 'd1', 'c1', 'm1')
        with self.assertRaises(ValueError):
            self.crypto.decrypt(wrong_dek, ct, nonce, 'd1', 'c1', 'm1')

    def test_tampered_ciphertext_fails(self):
        dek = self.crypto.generate_dek()
        ct, nonce = self.crypto.encrypt(dek, "hello", 'd1', 'c1', 'm1')
        tampered = bytearray(ct)
        tampered[0] ^= 0xFF
        with self.assertRaises(ValueError):
            self.crypto.decrypt(dek, bytes(tampered), nonce, 'd1', 'c1', 'm1')

    def test_aad_cross_conversation_fails(self):
        """Ciphertext from conversation A cannot be decrypted in conversation B."""
        dek = self.crypto.generate_dek()
        ct, nonce = self.crypto.encrypt(dek, "cross", 'domain', 'conv-A', 'msg-1')
        with self.assertRaises(ValueError):
            self.crypto.decrypt(dek, ct, nonce, 'domain', 'conv-B', 'msg-1')

    def test_aad_cross_domain_fails(self):
        """Ciphertext from domain A cannot be decrypted in domain B."""
        dek = self.crypto.generate_dek()
        ct, nonce = self.crypto.encrypt(dek, "cross", 'domain-A', 'conv', 'msg')
        with self.assertRaises(ValueError):
            self.crypto.decrypt(dek, ct, nonce, 'domain-B', 'conv', 'msg')

    def test_aad_cross_message_fails(self):
        """Ciphertext for message 1 cannot be decrypted as message 2."""
        dek = self.crypto.generate_dek()
        ct, nonce = self.crypto.encrypt(dek, "x", 'd', 'c', 'msg-1')
        with self.assertRaises(ValueError):
            self.crypto.decrypt(dek, ct, nonce, 'd', 'c', 'msg-2')

    def test_dek_wrap_unwrap_roundtrip(self):
        dek = self.crypto.generate_dek()
        wrapped = self.crypto.wrap_dek(dek, key_version=1)
        self.assertEqual(len(wrapped.ciphertext), AES_KEY_SIZE + 16)  # GCM tag
        self.assertEqual(len(wrapped.nonce), NONCE_SIZE)
        self.assertEqual(wrapped.key_version, 1)
        unwrapped = self.crypto.unwrap_dek(wrapped)
        self.assertEqual(dek, unwrapped)

    def test_dek_wrong_kek_fails(self):
        dek = self.crypto.generate_dek()
        wrapped = self.crypto.wrap_dek(dek)
        # Create a different KeyProvider (different KEK)
        tmp2 = Path(tempfile.mkdtemp())
        kp2 = KeyProvider(tmp2)
        crypto2 = ConversationCrypto(kp2)
        with self.assertRaises(ValueError):
            crypto2.unwrap_dek(wrapped)

    def test_dek_tampered_wrap_fails(self):
        dek = self.crypto.generate_dek()
        wrapped = self.crypto.wrap_dek(dek)
        tampered = WrappedDEK(
            ciphertext=wrapped.ciphertext[:-1] + b'X',
            nonce=wrapped.nonce, key_version=wrapped.key_version)
        with self.assertRaises(ValueError):
            self.crypto.unwrap_dek(tampered)


class ConversationServiceTests(unittest.TestCase):
    """Integration tests for the ConversationService."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data_dir = Path(self.tmp)
        self.svc = ConversationService(self.data_dir)

    def tearDown(self):
        self.svc.close()

    def test_create_and_get_conversation(self):
        self.svc.create_conversation('conv-1')
        conv = self.svc.get_conversation('conv-1')
        self.assertIsNotNone(conv)
        self.assertEqual(conv['id'], 'conv-1')
        self.assertEqual(conv['domain_id'], 'personal-default')

    def test_add_and_get_message(self):
        self.svc.create_conversation('conv-1')
        msg = self.svc.add_message('conv-1', 'human', 'Hello world')
        self.assertEqual(msg['role'], 'human')
        retrieved = self.svc.get_message('conv-1', msg['id'])
        self.assertEqual(retrieved['content'], 'Hello world')

    def test_message_encrypted_at_rest(self):
        """The stored payload must NOT contain the plaintext."""
        self.svc.create_conversation('conv-1')
        sentinel = 'BLAINE_SECRET_SENTINEL_unique_xyz_999'
        self.svc.add_message('conv-1', 'human', sentinel)

        # Read raw bytes from SQLite
        db = sqlite3.connect(str(self.data_dir / 'conversation.sqlite'))
        rows = db.execute(
            'SELECT content_enc, content_nonce, dek_wrapped FROM conversation_messages'
        ).fetchall()
        db.close()
        self.assertEqual(len(rows), 1)
        content_enc, content_nonce, dek_wrapped = rows[0]
        # The plaintext sentinel must NOT appear in any stored column
        self.assertNotIn(sentinel.encode(), content_enc)
        self.assertNotIn(sentinel.encode(), content_nonce)
        self.assertNotIn(sentinel.encode(), dek_wrapped)
        # The DEK itself should not be stored in plaintext (it's wrapped)
        self.assertNotIn(content_enc, dek_wrapped)

    def test_list_messages_ordered(self):
        self.svc.create_conversation('conv-1')
        self.svc.add_message('conv-1', 'human', 'first')
        self.svc.add_message('conv-1', 'agent', 'second')
        msgs = self.svc.list_messages('conv-1')
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]['content'], 'first')
        self.assertEqual(msgs[1]['content'], 'second')

    def test_task_link_persistence(self):
        self.svc.create_conversation('conv-1')
        msg = self.svc.add_message('conv-1', 'delegation', 'Delegating...')
        link = self.svc.link_task('conv-1', 'task-abc123', msg['id'])
        self.assertEqual(link['task_id'], 'task-abc123')
        links = self.svc.list_task_links('conv-1')
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]['task_id'], 'task-abc123')
        self.assertFalse(links[0]['result_surfaced'])

    def test_result_surfaced_tracking(self):
        self.svc.create_conversation('conv-1')
        msg = self.svc.add_message('conv-1', 'delegation', 'x')
        self.svc.link_task('conv-1', 'task-xyz', msg['id'])
        self.assertEqual(self.svc.find_unsurfaced_results('conv-1'), ['task-xyz'])
        self.svc.mark_result_surfaced('conv-1', 'task-xyz')
        self.assertEqual(self.svc.find_unsurfaced_results('conv-1'), [])

    def test_cross_conversation_isolation(self):
        """A message in conv-A is not visible from conv-B."""
        self.svc.create_conversation('conv-A')
        self.svc.create_conversation('conv-B')
        msg = self.svc.add_message('conv-A', 'human', 'secret in A')
        # Try to get it from conv-B
        result = self.svc.get_message('conv-B', msg['id'])
        self.assertIsNone(result)
        # List messages in B — empty
        self.assertEqual(self.svc.list_messages('conv-B'), [])

    def test_cross_conversation_task_isolation(self):
        """Task links in conv-A are not visible from conv-B."""
        self.svc.create_conversation('conv-A')
        self.svc.create_conversation('conv-B')
        msg = self.svc.add_message('conv-A', 'delegation', 'x')
        self.svc.link_task('conv-A', 'task-1', msg['id'])
        # conv-B has no task links
        self.assertEqual(self.svc.list_task_links('conv-B'), [])

    def test_durability_across_restart(self):
        """Conversation data survives a service restart (simulates process restart)."""
        self.svc.create_conversation('conv-durable')
        msg = self.svc.add_message('conv-durable', 'human', 'persist me')
        self.svc.link_task('conv-durable', 'task-persist', msg['id'])
        self.svc.close()

        # Reopen (simulates process restart)
        svc2 = ConversationService(self.data_dir)
        conv = svc2.get_conversation('conv-durable')
        self.assertIsNotNone(conv)
        messages = svc2.list_messages('conv-durable')
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['content'], 'persist me')
        links = svc2.list_task_links('conv-durable')
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]['task_id'], 'task-persist')
        svc2.close()

    def test_invalid_role_rejected(self):
        self.svc.create_conversation('conv-1')
        with self.assertRaises(ValueError):
            self.svc.add_message('conv-1', 'invalid_role', 'x')

    def test_message_in_nonexistent_conversation(self):
        with self.assertRaises(ValueError):
            self.svc.add_message('nonexistent', 'human', 'x')

    def test_key_version_stored(self):
        """key_version is persisted in the database row."""
        self.svc.create_conversation('conv-kv')
        self.svc.add_message('conv-kv', 'human', 'version test')
        db = sqlite3.connect(str(self.data_dir / 'conversation.sqlite'))
        row = db.execute(
            'SELECT dek_key_version FROM conversation_messages'
        ).fetchone()
        db.close()
        self.assertEqual(row[0], 1)


class ConversationNoMemoryRegressionTests(unittest.TestCase):
    """Verify PA-2 does not write to MIRIX or modify memory semantics."""

    def test_conversation_service_has_no_mirix_dependency(self):
        """The ConversationService must not import or call MirixContext."""
        import inspect
        source = inspect.getsource(ConversationService)
        self.assertNotIn('Mirix', source)
        self.assertNotIn('mirix', source)
        self.assertNotIn('memory/search', source)

    def test_conversation_service_has_no_task_lifecycle(self):
        """The ConversationService must not own Task lifecycle."""
        import inspect
        source = inspect.getsource(ConversationService)
        self.assertNotIn('restate', source.lower())
        self.assertNotIn('workflow', source)


if __name__ == '__main__':
    unittest.main()
