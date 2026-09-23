"""Durable encrypted Conversation persistence.

Conversation is NOT Task, NOT Memory, NOT a Restate workflow.
This module provides the repository boundary for:
  - conversation history (encrypted at rest);
  - Conversation↔Task provenance links;
  - key-management for application-layer AEAD.

Trust model:
  The trusted Personal Agent process holds the KEK and may decrypt
  Conversation content. Workers receive only bounded Task context,
  never the Conversation key. This is application-layer encryption
  at rest, NOT end-to-end encryption.

Cryptography:
  AES-256-GCM (via the `cryptography` library). Envelope encryption:
  a per-domain DEK encrypts message payloads; the KEK wraps the DEK.
  AAD binds ciphertext to (encryption_domain_id, conversation_id,
  message_id, schema_version) to prevent cross-scope replay.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# --- Constants ---

SCHEMA_VERSION = 1
AES_KEY_SIZE = 32  # 256 bits
NONCE_SIZE = 12    # 96 bits (GCM standard)
ENCRYPTION_DOMAIN_DEFAULT = 'personal-default'


# --- Key Management ---

class KeyProvider:
    """Loads and caches the KEK from a local runtime credential file.

    The KEK is a 32-byte key stored at:
      <key_dir>/conversation-kek.key  (mode 0600, parent dir 0700)

    Key material is stored OUTSIDE the Conversation data directory to
    preserve backup isolation: a data-only backup of conversation.sqlite
    does not contain the key needed to decrypt it.

    Default key location: ~/.config/blaine/secrets/ (existing Blaine
    secret boundary). Override with BLAINE_CONVERSATION_KEY_DIR env var.

    Initialization rule:
      - If the key file exists: load it.
      - If the key file is missing AND the store is empty: generate a new KEK.
      - If the key file is missing AND encrypted data exists: FAIL CLOSED.
        Never silently regenerate a key over existing encrypted data.

    It is never stored in the database, never logged, never committed.
    """

    def __init__(self, key_dir: Path):
        self._key_file = key_dir / 'conversation-kek.key'
        self._kek: bytes | None = None

    def has_existing_key(self) -> bool:
        """Check if a KEK file exists (without loading it)."""
        return self._key_file.exists()

    def load_or_create(self, store_has_data: bool = False) -> bytes:
        if self._kek is not None:
            return self._kek
        if self._key_file.exists():
            self._kek = self._key_file.read_bytes()
            if len(self._kek) != AES_KEY_SIZE:
                raise ValueError('KEK file has invalid size')
        else:
            if store_has_data:
                raise KeyError(
                    'Conversation KEK is missing but encrypted data exists. '
                    'Refusing to generate a replacement key. '
                    'Restore the original key from your separate key backup. '
                    'Key location: ' + str(self._key_file)
                )
            self._kek = secrets.token_bytes(AES_KEY_SIZE)
            self._key_file.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(self._key_file.parent, 0o700)
            self._key_file.write_bytes(self._kek)
            os.chmod(self._key_file, 0o600)
        return self._kek

    def load(self, store_has_data: bool = False) -> bytes:
        """Load the KEK, failing closed if missing and data exists."""
        if self._kek is not None:
            return self._kek
        return self.load_or_create(store_has_data=store_has_data)

    @property
    def kek(self) -> bytes:
        return self.load_or_create()

    @property
    def key_path(self) -> Path:
        return self._key_file


# --- Envelope Encryption ---

@dataclass(frozen=True)
class WrappedDEK:
    """A DEK wrapped by the KEK. Stored in the database alongside key_version."""
    ciphertext: bytes   # wrapped DEK (AES-256-GCM output)
    nonce: bytes        # 12-byte nonce for wrapping
    key_version: int


class ConversationCrypto:
    """AES-256-GCM envelope encryption for Conversation payloads.

    - DEK (32 bytes) encrypts message content.
    - KEK wraps the DEK for storage.
    - AAD binds each ciphertext to its stable identity so ciphertext
      cannot be silently moved between messages/conversations/domains.
    """

    def __init__(self, key_provider: KeyProvider):
        self._kp = key_provider

    def _aad(self, domain_id: str, conversation_id: str, message_id: str) -> bytes:
        """Build the Additional Authenticated Data binding ciphertext to identity.

        Format: 1 byte schema_version + 32 bytes domain + 32 bytes conversation
                + 32 bytes message = 97 bytes total.
        Each string field is zero-padded to exactly 32 bytes.
        """
        d = domain_id.encode('utf-8')[:32].ljust(32, b'\x00')
        c = conversation_id.encode('utf-8')[:32].ljust(32, b'\x00')
        m = message_id.encode('utf-8')[:32].ljust(32, b'\x00')
        return struct.pack('>B', SCHEMA_VERSION) + d + c + m

    def generate_dek(self) -> bytes:
        return secrets.token_bytes(AES_KEY_SIZE)

    def wrap_dek(self, dek: bytes, key_version: int = 1) -> WrappedDEK:
        """Wrap a DEK with the KEK (AES-256-GCM)."""
        kek = self._kp.kek
        nonce = secrets.token_bytes(NONCE_SIZE)
        aad = struct.pack('>B', key_version)  # bind key_version to wrap
        cipher = AESGCM(kek)
        ciphertext = cipher.encrypt(nonce, dek, aad)
        return WrappedDEK(ciphertext=ciphertext, nonce=nonce, key_version=key_version)

    def unwrap_dek(self, wrapped: WrappedDEK) -> bytes:
        """Unwrap a DEK with the KEK. Fails closed on tamper/wrong key."""
        kek = self._kp.kek
        aad = struct.pack('>B', wrapped.key_version)
        cipher = AESGCM(kek)
        try:
            return cipher.decrypt(wrapped.nonce, wrapped.ciphertext, aad)
        except Exception:
            raise ValueError('DEK unwrap failed: wrong KEK or tampered ciphertext')

    def encrypt(self, dek: bytes, plaintext: str,
                domain_id: str, conversation_id: str, message_id: str) -> tuple[bytes, bytes]:
        """Encrypt a message payload. Returns (ciphertext, nonce)."""
        nonce = secrets.token_bytes(NONCE_SIZE)
        aad = self._aad(domain_id, conversation_id, message_id)
        cipher = AESGCM(dek)
        ciphertext = cipher.encrypt(nonce, plaintext.encode('utf-8'), aad)
        return ciphertext, nonce

    def decrypt(self, dek: bytes, ciphertext: bytes, nonce: bytes,
                domain_id: str, conversation_id: str, message_id: str) -> str:
        """Decrypt a message payload. Fails closed on tamper/AAD mismatch."""
        aad = self._aad(domain_id, conversation_id, message_id)
        cipher = AESGCM(dek)
        try:
            return cipher.decrypt(nonce, ciphertext, aad).decode('utf-8')
        except Exception:
            raise ValueError('Decryption failed: wrong key, tampered ciphertext, or AAD mismatch')


# --- Conversation Service ---

class ConversationService:
    """Durable Conversation persistence with encrypted payloads.

    SQLite is the durable store (consistent with the existing fixture.sqlite
    pattern). The database lives at <data_dir>/conversation.sqlite.

    Tables:
      conversations(id, domain_id, created_at, title_enc, title_nonce)
      conversation_messages(id, conversation_id, role, created_at,
                            dek_wrapped, dek_nonce, dek_key_version,
                            content_enc, content_nonce)
      conversation_task_links(conversation_id, task_id, message_id,
                              created_at, result_surfaced)
    """

    def __init__(self, data_dir: Path, key_dir: Path | None = None):
        self._data_dir = data_dir
        self._db_path = data_dir / 'conversation.sqlite'
        # Key material lives OUTSIDE the data directory (backup isolation).
        # Default: ~/.config/blaine/secrets/ (existing Blaine secret boundary).
        # Override: BLAINE_CONVERSATION_KEY_DIR env var.
        if key_dir is None:
            env_key_dir = os.environ.get('BLAINE_CONVERSATION_KEY_DIR')
            if env_key_dir:
                key_dir = Path(env_key_dir)
            else:
                key_dir = Path.home() / '.config' / 'blaine' / 'secrets'
        self._key_provider = KeyProvider(key_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._db.execute('PRAGMA journal_mode=WAL')
        self._init_schema()
        # Key initialization:
        # - If encrypted data exists: the key MUST be present (fail closed).
        # - If the store is empty: generate a new key (first-time setup).
        if self._store_has_data():
            self._key_provider.load(store_has_data=True)
        else:
            self._key_provider.load_or_create(store_has_data=False)
        self._crypto = ConversationCrypto(self._key_provider)

    def _store_has_data(self) -> bool:
        """Check if encrypted Conversation data already exists."""
        row = self._db.execute(
            'SELECT 1 FROM conversation_messages LIMIT 1').fetchone()
        return row is not None

    def _init_schema(self):
        self._db.executescript('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                domain_id TEXT NOT NULL DEFAULT 'personal-default',
                created_at TEXT NOT NULL,
                title_enc BLOB,
                title_nonce BLOB
            );
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id),
                role TEXT NOT NULL CHECK(role IN ('human','agent','system','delegation','result')),
                created_at TEXT NOT NULL,
                dek_wrapped BLOB NOT NULL,
                dek_nonce BLOB NOT NULL,
                dek_key_version INTEGER NOT NULL DEFAULT 1,
                content_enc BLOB NOT NULL,
                content_nonce BLOB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conversation_task_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL REFERENCES conversations(id),
                task_id TEXT NOT NULL,
                message_id TEXT NOT NULL REFERENCES conversation_messages(id),
                created_at TEXT NOT NULL,
                result_surfaced INTEGER NOT NULL DEFAULT 0,
                UNIQUE(conversation_id, task_id)
            );
            CREATE INDEX IF NOT EXISTS idx_msg_conv
                ON conversation_messages(conversation_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_task_link_conv
                ON conversation_task_links(conversation_id);
        ''')
        self._db.commit()

    # --- Conversation CRUD ---

    def create_conversation(self, conversation_id: str,
                            domain_id: str = ENCRYPTION_DOMAIN_DEFAULT) -> dict:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        self._db.execute(
            'INSERT INTO conversations (id, domain_id, created_at) VALUES (?, ?, ?)',
            (conversation_id, domain_id, now))
        self._db.commit()
        return {'id': conversation_id, 'domain_id': domain_id, 'created_at': now}

    def get_conversation(self, conversation_id: str) -> dict | None:
        row = self._db.execute(
            'SELECT id, domain_id, created_at, title_enc, title_nonce FROM conversations WHERE id = ?',
            (conversation_id,)).fetchone()
        if row is None:
            return None
        return {'id': row[0], 'domain_id': row[1], 'created_at': row[2]}

    def list_conversations(self, limit: int = 50) -> list[dict]:
        rows = self._db.execute(
            'SELECT id, domain_id, created_at FROM conversations ORDER BY created_at DESC LIMIT ?',
            (limit,)).fetchall()
        return [{'id': r[0], 'domain_id': r[1], 'created_at': r[2]} for r in rows]

    # --- Message CRUD (encrypted) ---

    VALID_ROLES = frozenset(('human', 'agent', 'system', 'delegation', 'result'))

    def add_message(self, conversation_id: str, role: str,
                    content: str, message_id: str | None = None) -> dict:
        """Add an encrypted message to a conversation. Returns message metadata."""
        from datetime import datetime, timezone
        import uuid
        now = datetime.now(timezone.utc).isoformat()
        if message_id is None:
            message_id = 'msg-' + uuid.uuid4().hex[:16]

        if role not in self.VALID_ROLES:
            raise ValueError(f'role must be one of {sorted(self.VALID_ROLES)}')

        # Verify conversation exists
        conv = self.get_conversation(conversation_id)
        if conv is None:
            raise ValueError(f'Conversation {conversation_id} not found')

        domain_id = conv['domain_id']

        # Generate DEK, encrypt content, wrap DEK
        dek = self._crypto.generate_dek()
        content_enc, content_nonce = self._crypto.encrypt(
            dek, content, domain_id, conversation_id, message_id)
        wrapped_dek = self._crypto.wrap_dek(dek, key_version=1)

        self._db.execute('''
            INSERT INTO conversation_messages
                (id, conversation_id, role, created_at,
                 dek_wrapped, dek_nonce, dek_key_version, content_enc, content_nonce)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (message_id, conversation_id, role, now,
             wrapped_dek.ciphertext, wrapped_dek.nonce, wrapped_dek.key_version,
             content_enc, content_nonce))
        self._db.commit()

        return {'id': message_id, 'conversation_id': conversation_id,
                'role': role, 'created_at': now}

    def get_message(self, conversation_id: str, message_id: str) -> dict | None:
        """Decrypt and return a message. Fails closed on tamper/wrong key."""
        row = self._db.execute('''
            SELECT id, conversation_id, role, created_at,
                   dek_wrapped, dek_nonce, dek_key_version, content_enc, content_nonce
            FROM conversation_messages WHERE conversation_id = ? AND id = ?''',
            (conversation_id, message_id)).fetchone()
        if row is None:
            return None

        wrapped = WrappedDEK(ciphertext=row[4], nonce=row[5], key_version=row[6])
        dek = self._crypto.unwrap_dek(wrapped)
        content = self._crypto.decrypt(dek, row[7], row[8],
                                       self._get_domain(conversation_id), conversation_id, row[0])
        return {'id': row[0], 'conversation_id': row[1], 'role': row[2],
                'created_at': row[3], 'content': content}

    def list_messages(self, conversation_id: str,
                      limit: int = 100) -> list[dict]:
        """Return all messages in a conversation, decrypted."""
        rows = self._db.execute('''
            SELECT id, role, created_at, dek_wrapped, dek_nonce,
                   dek_key_version, content_enc, content_nonce
            FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
            LIMIT ?''', (conversation_id, limit)).fetchall()
        domain_id = self._get_domain(conversation_id)
        results = []
        for row in rows:
            wrapped = WrappedDEK(ciphertext=row[3], nonce=row[4], key_version=row[5])
            dek = self._crypto.unwrap_dek(wrapped)
            content = self._crypto.decrypt(dek, row[6], row[7],
                                           domain_id, conversation_id, row[0])
            results.append({'id': row[0], 'role': row[1], 'created_at': row[2], 'content': content})
        return results

    # --- Task Links (provenance) ---

    def link_task(self, conversation_id: str, task_id: str,
                  message_id: str) -> dict:
        """Record a Conversation↔Task provenance link."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        try:
            self._db.execute('''
                INSERT INTO conversation_task_links
                    (conversation_id, task_id, message_id, created_at, result_surfaced)
                VALUES (?, ?, ?, ?, 0)''',
                (conversation_id, task_id, message_id, now))
            self._db.commit()
        except sqlite3.IntegrityError:
            pass  # Already linked (idempotent)
        return {'conversation_id': conversation_id, 'task_id': task_id,
                'message_id': message_id, 'created_at': now, 'result_surfaced': False}

    def list_task_links(self, conversation_id: str) -> list[dict]:
        """All Task links for a conversation (durable provenance)."""
        rows = self._db.execute('''
            SELECT task_id, message_id, created_at, result_surfaced
            FROM conversation_task_links WHERE conversation_id = ?
            ORDER BY created_at ASC''', (conversation_id,)).fetchall()
        return [{'task_id': r[0], 'message_id': r[1], 'created_at': r[2],
                 'result_surfaced': bool(r[3])} for r in rows]

    def mark_result_surfaced(self, conversation_id: str, task_id: str) -> None:
        """Mark that a Task's result has been surfaced in the conversation."""
        self._db.execute('''
            UPDATE conversation_task_links SET result_surfaced = 1
            WHERE conversation_id = ? AND task_id = ?''',
            (conversation_id, task_id))
        self._db.commit()

    def find_unsurfaced_results(self, conversation_id: str) -> list[str]:
        """Task IDs whose results have not yet been surfaced in this conversation."""
        rows = self._db.execute('''
            SELECT task_id FROM conversation_task_links
            WHERE conversation_id = ? AND result_surfaced = 0''',
            (conversation_id,)).fetchall()
        return [r[0] for r in rows]

    # --- Internal ---

    def _get_domain(self, conversation_id: str) -> str:
        row = self._db.execute(
            'SELECT domain_id FROM conversations WHERE id = ?',
            (conversation_id,)).fetchone()
        return row[0] if row else ENCRYPTION_DOMAIN_DEFAULT

    def close(self):
        self._db.close()
