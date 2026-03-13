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
Cryptographic Utilities for MAVIS Demo

Provides utilities for:
- Image hash generation (SHA-256)
- Signature verification
- Certificate encryption/decryption using server keys
"""

import hashlib
import base64
import os
from typing import Tuple, Optional
from io import BytesIO

from PIL import Image
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend


class CryptoUtils:
    """
    Cryptographic utilities for the MAVIS demo.

    Handles:
    - Image hashing
    - Signature verification
    - Symmetric encryption for certificates (AES-GCM)
    """

    # Server encryption key (in production, this would be securely stored)
    # Using a fixed key for demo purposes - 256-bit key
    _SERVER_KEY: bytes = hashlib.sha256(b"MAVIS_DEMO_SERVER_KEY_2026").digest()

    @staticmethod
    def hash_image(image: Image.Image) -> str:
        """
        Generate SHA-256 hash of an image.

        The hash is computed from the raw pixel data to ensure
        consistency regardless of file format or metadata.

        Args:
            image: PIL Image object

        Returns:
            Hex string of the SHA-256 hash
        """
        # Convert to RGB to ensure consistent hashing
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Hash the raw pixel data
        pixel_data = image.tobytes()
        return hashlib.sha256(pixel_data).hexdigest()

    @staticmethod
    def hash_image_bytes(image_bytes: bytes) -> str:
        """
        Generate SHA-256 hash from image bytes.

        Args:
            image_bytes: Raw image file bytes

        Returns:
            Hex string of the SHA-256 hash
        """
        image = Image.open(BytesIO(image_bytes))
        return CryptoUtils.hash_image(image)

    @staticmethod
    def hash_string(data: str) -> str:
        """
        Generate SHA-256 hash of a string.

        Args:
            data: String to hash

        Returns:
            Hex string of the SHA-256 hash
        """
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        """
        Generate SHA-256 hash of bytes.

        Args:
            data: Bytes to hash

        Returns:
            Hex string of the SHA-256 hash
        """
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def verify_signature(
        data: bytes, signature: bytes, public_key_pem: bytes
    ) -> bool:
        """
        Verify a signature using a public key.

        Args:
            data: The original data that was signed
            signature: The signature to verify
            public_key_pem: Public key in PEM format

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            public_key = serialization.load_pem_public_key(
                public_key_pem, backend=default_backend()
            )
            public_key.verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False

    @staticmethod
    def verify_image_signature(
        image_hash: str, signature: bytes, public_key_pem: bytes
    ) -> bool:
        """
        Verify an image signature.

        Args:
            image_hash: SHA-256 hash of the image (hex string)
            signature: The signature to verify
            public_key_pem: Public key in PEM format

        Returns:
            True if signature is valid, False otherwise
        """
        return CryptoUtils.verify_signature(
            image_hash.encode("utf-8"), signature, public_key_pem
        )

    @classmethod
    def encrypt_certificate(cls, certificate_data: str) -> str:
        """
        Encrypt certificate data using AES-GCM.

        Args:
            certificate_data: Certificate string (typically hex-encoded)

        Returns:
            Base64-encoded encrypted data (nonce + ciphertext + tag)
        """
        aesgcm = AESGCM(cls._SERVER_KEY)
        nonce = os.urandom(12)  # 96-bit nonce for AES-GCM

        ciphertext = aesgcm.encrypt(
            nonce, certificate_data.encode("utf-8"), None
        )

        # Combine nonce and ciphertext
        encrypted = nonce + ciphertext
        return base64.b64encode(encrypted).decode("utf-8")

    @classmethod
    def decrypt_certificate(cls, encrypted_data: str) -> Optional[str]:
        """
        Decrypt certificate data using AES-GCM.

        Args:
            encrypted_data: Base64-encoded encrypted data

        Returns:
            Decrypted certificate string, or None if decryption fails
        """
        try:
            encrypted = base64.b64decode(encrypted_data)
            nonce = encrypted[:12]
            ciphertext = encrypted[12:]

            aesgcm = AESGCM(cls._SERVER_KEY)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode("utf-8")
        except Exception:
            return None

