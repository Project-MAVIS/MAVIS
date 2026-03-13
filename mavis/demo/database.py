# Copyright (c) 2026 Project MAVIS Authors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, subject to the conditions in the LICENSE file.
#
# See the LICENSE file for more details.

"""
SQLite Database and Local Blob Storage for MAVIS Demo

Provides persistent storage for:
- Registered devices (user_id, device_id -> public_key)
- Certificates (cert_hash -> encrypted_cert)
- Original images stored as files on local filesystem
"""

import sqlite3
import shutil
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path

from PIL import Image


# Default paths for demo data
DEFAULT_DATA_DIR = Path(__file__).parent / ".mavis_demo_data"
DEFAULT_DB_NAME = "mavis_demo.db"
DEFAULT_BLOB_DIR = "images"


@dataclass
class DeviceRecord:
    """Record of a registered device."""

    device_id: str
    user_id: str
    username: str
    device_name: str
    public_key_pem: bytes
    registered_at: datetime


@dataclass
class CertificateRecord:
    """Record of a stored certificate."""

    cert_hash: str
    encrypted_certificate: str
    image_id: int
    device_id: str
    created_at: datetime


@dataclass
class ImageRecord:
    """Record of an original image."""

    cert_hash: str
    image_path: str
    original_filename: Optional[str]
    created_at: datetime


class DemoDatabase:
    """
    SQLite database with local filesystem blob storage for the MAVIS demo.

    This provides persistent storage that survives application restarts.
    Images are stored as files in a local directory for efficient blob handling.
    """

    _instance: Optional["DemoDatabase"] = None

    def __new__(cls) -> "DemoDatabase":
        """Singleton pattern to ensure single database instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, data_dir: Optional[Path] = None):
        if self._initialized:
            return

        # Set up paths
        self._data_dir = data_dir or DEFAULT_DATA_DIR
        self._db_path = self._data_dir / DEFAULT_DB_NAME
        self._blob_dir = self._data_dir / DEFAULT_BLOB_DIR

        # Create directories
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._blob_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()
        self._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Devices table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    device_name TEXT NOT NULL,
                    public_key_pem BLOB NOT NULL,
                    registered_at TEXT NOT NULL
                )
            """
            )

            # Certificates table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS certificates (
                    cert_hash TEXT PRIMARY KEY,
                    encrypted_certificate TEXT NOT NULL,
                    image_id INTEGER NOT NULL,
                    device_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (device_id) REFERENCES devices(device_id)
                )
            """
            )

            # Images table (metadata only, actual files stored on disk)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS images (
                    cert_hash TEXT PRIMARY KEY,
                    image_path TEXT NOT NULL,
                    original_filename TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (cert_hash) REFERENCES certificates(cert_hash)
                )
            """
            )

            # Image counter table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS counters (
                    name TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                )
            """
            )

            # Initialize image counter if not exists
            cursor.execute(
                """
                INSERT OR IGNORE INTO counters (name, value) VALUES ('image_id', 0)
            """
            )

            conn.commit()

    def reset(self):
        """Reset the database and blob storage (useful for testing)."""
        # Clear blob storage
        if self._blob_dir.exists():
            shutil.rmtree(self._blob_dir)
        self._blob_dir.mkdir(parents=True, exist_ok=True)

        # Clear database tables
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM images")
            cursor.execute("DELETE FROM certificates")
            cursor.execute("DELETE FROM devices")
            cursor.execute("UPDATE counters SET value = 0 WHERE name = 'image_id'")
            conn.commit()

    # ==================== Device Operations ====================

    def register_device(
        self,
        device_id: str,
        user_id: str,
        username: str,
        device_name: str,
        public_key_pem: bytes,
    ) -> DeviceRecord:
        """
        Register a new device.

        Args:
            device_id: Unique device identifier
            user_id: User identifier
            username: Username of device owner
            device_name: Name/model of device
            public_key_pem: Device's public key in PEM format

        Returns:
            The created DeviceRecord
        """
        registered_at = datetime.now()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO devices
                (device_id, user_id, username, device_name, public_key_pem, registered_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    device_id,
                    user_id,
                    username,
                    device_name,
                    public_key_pem,
                    registered_at.isoformat(),
                ),
            )
            conn.commit()

        return DeviceRecord(
            device_id=device_id,
            user_id=user_id,
            username=username,
            device_name=device_name,
            public_key_pem=public_key_pem,
            registered_at=registered_at,
        )

    def get_device(self, device_id: str) -> Optional[DeviceRecord]:
        """Get a device by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
            row = cursor.fetchone()

            if row:
                return DeviceRecord(
                    device_id=row["device_id"],
                    user_id=row["user_id"],
                    username=row["username"],
                    device_name=row["device_name"],
                    public_key_pem=row["public_key_pem"],
                    registered_at=datetime.fromisoformat(row["registered_at"]),
                )
        return None

    def get_device_public_key(self, device_id: str) -> Optional[bytes]:
        """Get the public key for a device."""
        device = self.get_device(device_id)
        return device.public_key_pem if device else None

    def is_device_registered(self, device_id: str) -> bool:
        """Check if a device is registered."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM devices WHERE device_id = ?", (device_id,))
            return cursor.fetchone() is not None

    # ==================== Certificate Operations ====================

    def get_next_image_id(self) -> int:
        """Get the next available image ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE counters SET value = value + 1 WHERE name = 'image_id'"
            )
            cursor.execute("SELECT value FROM counters WHERE name = 'image_id'")
            row = cursor.fetchone()
            conn.commit()
            return row["value"] if row else 1

    def store_certificate(
        self,
        cert_hash: str,
        encrypted_certificate: str,
        image_id: int,
        device_id: str,
    ) -> CertificateRecord:
        """
        Store an encrypted certificate.

        Args:
            cert_hash: Hash of the certificate
            encrypted_certificate: Encrypted certificate string
            image_id: Associated image ID
            device_id: Device that created the certificate

        Returns:
            The created CertificateRecord
        """
        created_at = datetime.now()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO certificates
                (cert_hash, encrypted_certificate, image_id, device_id, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    cert_hash,
                    encrypted_certificate,
                    image_id,
                    device_id,
                    created_at.isoformat(),
                ),
            )
            conn.commit()

        return CertificateRecord(
            cert_hash=cert_hash,
            encrypted_certificate=encrypted_certificate,
            image_id=image_id,
            device_id=device_id,
            created_at=created_at,
        )

    def get_certificate(self, cert_hash: str) -> Optional[CertificateRecord]:
        """Get a certificate by its hash."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM certificates WHERE cert_hash = ?", (cert_hash,)
            )
            row = cursor.fetchone()

            if row:
                return CertificateRecord(
                    cert_hash=row["cert_hash"],
                    encrypted_certificate=row["encrypted_certificate"],
                    image_id=row["image_id"],
                    device_id=row["device_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
        return None

    # ==================== Image Operations ====================

    def store_image(
        self,
        cert_hash: str,
        image: Image.Image,
        original_filename: Optional[str] = None,
    ) -> ImageRecord:
        """
        Store an original image to the local filesystem.

        Args:
            cert_hash: Certificate hash (used as key and filename)
            image: PIL Image object
            original_filename: Original filename if available

        Returns:
            The created ImageRecord
        """
        created_at = datetime.now()

        # Generate filename using cert_hash
        image_filename = f"{cert_hash}.png"
        image_path = self._blob_dir / image_filename

        # Save image to filesystem
        image.save(str(image_path), format="PNG")

        # Store metadata in database
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO images
                (cert_hash, image_path, original_filename, created_at)
                VALUES (?, ?, ?, ?)
            """,
                (
                    cert_hash,
                    str(image_path),
                    original_filename,
                    created_at.isoformat(),
                ),
            )
            conn.commit()

        return ImageRecord(
            cert_hash=cert_hash,
            image_path=str(image_path),
            original_filename=original_filename,
            created_at=created_at,
        )

    def get_image(self, cert_hash: str) -> Optional[Image.Image]:
        """Get an original image by certificate hash."""
        record = self.get_image_record(cert_hash)
        if record:
            image_path = Path(record.image_path)
            if image_path.exists():
                return Image.open(image_path)
        return None

    def get_image_record(self, cert_hash: str) -> Optional[ImageRecord]:
        """Get an image record by certificate hash."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM images WHERE cert_hash = ?", (cert_hash,))
            row = cursor.fetchone()

            if row:
                return ImageRecord(
                    cert_hash=row["cert_hash"],
                    image_path=row["image_path"],
                    original_filename=row["original_filename"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
        return None

    # ==================== Lookup Operations ====================

    def lookup_by_cert_hash(
        self, cert_hash: str
    ) -> Optional[Tuple[CertificateRecord, ImageRecord]]:
        """
        Look up both certificate and image by certificate hash.

        This is used in the WhatsApp scenario where EXIF is stripped
        but the QR code hash can still be extracted.

        Args:
            cert_hash: Hash extracted from the QR code

        Returns:
            Tuple of (CertificateRecord, ImageRecord) or None
        """
        cert_record = self.get_certificate(cert_hash)
        image_record = self.get_image_record(cert_hash)

        if cert_record and image_record:
            return cert_record, image_record
        return None

    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as count FROM devices")
            devices_count = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM certificates")
            certs_count = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM images")
            images_count = cursor.fetchone()["count"]

            return {
                "devices": devices_count,
                "certificates": certs_count,
                "images": images_count,
            }
