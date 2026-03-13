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
Secure Enclave Emulator

Emulates the iPhone Secure Enclave functionality for the MAVIS demo.
The Secure Enclave:
- Generates and stores RSA key pairs
- Signs data using the private key (never exposed)
- Provides access to the public key for verification
"""

import uuid
import hashlib
from typing import Tuple, Optional
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend


@dataclass
class DeviceInfo:
    """Information about a registered device."""

    device_id: str
    user_id: str
    username: str
    device_name: str
    public_key_pem: bytes
    # Private key is stored internally, never exposed
    _private_key: rsa.RSAPrivateKey = field(repr=False)


class SecureEnclave:
    """
    Emulates iPhone Secure Enclave for cryptographic operations.

    The Secure Enclave is a hardware-based key manager that's isolated
    from the main processor. It generates and stores cryptographic keys,
    and performs signing operations without ever exposing the private key.
    """

    def __init__(self):
        self._device: Optional[DeviceInfo] = None

    @property
    def is_initialized(self) -> bool:
        """Check if the Secure Enclave has been initialized with a device."""
        return self._device is not None

    @property
    def device_id(self) -> Optional[str]:
        """Get the device ID if initialized."""
        return self._device.device_id if self._device else None

    @property
    def user_id(self) -> Optional[str]:
        """Get the user ID if initialized."""
        return self._device.user_id if self._device else None

    @property
    def username(self) -> Optional[str]:
        """Get the username if initialized."""
        return self._device.username if self._device else None

    @property
    def device_name(self) -> Optional[str]:
        """Get the device name if initialized."""
        return self._device.device_name if self._device else None

    def initialize_device(
        self, username: str, device_name: str = "iPhone 15 Pro"
    ) -> Tuple[str, str, bytes]:
        """
        Initialize the Secure Enclave with a new device.

        This generates a new RSA key pair and stores it securely.
        The private key never leaves the Secure Enclave.

        Args:
            username: The username of the device owner
            device_name: Name/model of the device

        Returns:
            Tuple of (device_id, user_id, public_key_pem)
        """
        # Generate unique IDs
        device_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        # Generate RSA key pair (2048 bits for good security/performance balance)
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )

        # Extract public key in PEM format
        public_key_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        # Store device info (private key stays internal)
        self._device = DeviceInfo(
            device_id=device_id,
            user_id=user_id,
            username=username,
            device_name=device_name,
            public_key_pem=public_key_pem,
            _private_key=private_key,
        )

        return device_id, user_id, public_key_pem

    def get_public_key(self) -> bytes:
        """
        Get the public key in PEM format.

        This is the only key that can be shared externally.

        Returns:
            Public key in PEM format

        Raises:
            RuntimeError: If the Secure Enclave is not initialized
        """
        if not self._device:
            raise RuntimeError("Secure Enclave not initialized. Call initialize_device first.")
        return self._device.public_key_pem

    def sign_data(self, data: bytes) -> bytes:
        """
        Sign data using the Secure Enclave's private key.

        The signing operation happens entirely within the Secure Enclave.
        The private key is never exposed.

        Args:
            data: The data to sign

        Returns:
            The signature bytes

        Raises:
            RuntimeError: If the Secure Enclave is not initialized
        """
        if not self._device:
            raise RuntimeError("Secure Enclave not initialized. Call initialize_device first.")

        signature = self._device._private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return signature

    def sign_image_hash(self, image_hash: str) -> bytes:
        """
        Sign an image hash.

        This is the primary operation used when capturing an image.
        The image hash is signed to prove it was captured by this device.

        Args:
            image_hash: SHA-256 hash of the image (hex string)

        Returns:
            The signature bytes
        """
        return self.sign_data(image_hash.encode("utf-8"))

