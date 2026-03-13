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
In-Memory Database for MAVIS Demo

Provides simple storage for:
- Registered devices (user_id, device_id -> public_key)
- Certificates (cert_hash -> encrypted_cert)
- Original images (cert_hash -> image_bytes)
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from datetime import datetime
from io import BytesIO

from PIL import Image


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
    image_bytes: bytes
    original_filename: Optional[str]
    created_at: datetime


class DemoDatabase:
    """
    In-memory database for the MAVIS demo.

    This simulates the server-side storage that would be used
    in a production deployment.
    """

    _instance: Optional["DemoDatabase"] = None

    def __new__(cls) -> "DemoDatabase":
        """Singleton pattern to ensure single database instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._devices: Dict[str, DeviceRecord] = {}  # device_id -> DeviceRecord
        self._certificates: Dict[str, CertificateRecord] = {}  # cert_hash -> CertificateRecord
        self._images: Dict[str, ImageRecord] = {}  # cert_hash -> ImageRecord
        self._image_counter: int = 0
        self._initialized = True

    def reset(self):
        """Reset the database (useful for testing)."""
        self._devices.clear()
        self._certificates.clear()
        self._images.clear()
        self._image_counter = 0

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
        record = DeviceRecord(
            device_id=device_id,
            user_id=user_id,
            username=username,
            device_name=device_name,
            public_key_pem=public_key_pem,
            registered_at=datetime.now(),
        )
        self._devices[device_id] = record
        return record

    def get_device(self, device_id: str) -> Optional[DeviceRecord]:
        """Get a device by ID."""
        return self._devices.get(device_id)

    def get_device_public_key(self, device_id: str) -> Optional[bytes]:
        """Get the public key for a device."""
        device = self._devices.get(device_id)
        return device.public_key_pem if device else None

    def is_device_registered(self, device_id: str) -> bool:
        """Check if a device is registered."""
        return device_id in self._devices

    # ==================== Certificate Operations ====================

    def get_next_image_id(self) -> int:
        """Get the next available image ID."""
        self._image_counter += 1
        return self._image_counter

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
        record = CertificateRecord(
            cert_hash=cert_hash,
            encrypted_certificate=encrypted_certificate,
            image_id=image_id,
            device_id=device_id,
            created_at=datetime.now(),
        )
        self._certificates[cert_hash] = record
        return record

    def get_certificate(self, cert_hash: str) -> Optional[CertificateRecord]:
        """Get a certificate by its hash."""
        return self._certificates.get(cert_hash)

    # ==================== Image Operations ====================

    def store_image(
        self,
        cert_hash: str,
        image: Image.Image,
        original_filename: Optional[str] = None,
    ) -> ImageRecord:
        """
        Store an original image.

        Args:
            cert_hash: Certificate hash (used as key)
            image: PIL Image object
            original_filename: Original filename if available

        Returns:
            The created ImageRecord
        """
        # Convert image to bytes
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        record = ImageRecord(
            cert_hash=cert_hash,
            image_bytes=image_bytes,
            original_filename=original_filename,
            created_at=datetime.now(),
        )
        self._images[cert_hash] = record
        return record

    def get_image(self, cert_hash: str) -> Optional[Image.Image]:
        """Get an original image by certificate hash."""
        record = self._images.get(cert_hash)
        if record:
            return Image.open(BytesIO(record.image_bytes))
        return None

    def get_image_record(self, cert_hash: str) -> Optional[ImageRecord]:
        """Get an image record by certificate hash."""
        return self._images.get(cert_hash)

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
        cert_record = self._certificates.get(cert_hash)
        image_record = self._images.get(cert_hash)

        if cert_record and image_record:
            return cert_record, image_record
        return None

    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        return {
            "devices": len(self._devices),
            "certificates": len(self._certificates),
            "images": len(self._images),
        }

