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
Certificate Handling Utilities for MAVIS Demo

Provides utilities for creating, serializing, and hashing certificates.
This module provides a standalone implementation that doesn't depend on
the Django models from the main certificate module.
"""

import struct
import time
import hashlib
from dataclasses import dataclass
from typing import Tuple, Dict, Any
from datetime import datetime


@dataclass
class DemoCertificate:
    """Certificate structure for the MAVIS demo."""

    cert_len: int
    timestamp: int
    image_id: int
    user_id: int
    device_id: int
    username: str
    device_name: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert certificate to a dictionary for display."""
        return {
            "cert_len": self.cert_len,
            "timestamp": self.timestamp,
            "timestamp_readable": datetime.fromtimestamp(self.timestamp).isoformat(),
            "image_id": self.image_id,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "username": self.username,
            "device_name": self.device_name,
        }

    def __str__(self) -> str:
        return (
            f"Certificate:\n"
            f"  Length: {self.cert_len} bytes\n"
            f"  Timestamp: {datetime.fromtimestamp(self.timestamp).isoformat()}\n"
            f"  Image ID: {self.image_id}\n"
            f"  User ID: {self.user_id}\n"
            f"  Device ID: {self.device_id}\n"
            f"  Username: {self.username}\n"
            f"  Device Name: {self.device_name}"
        )


class CertificateUtils:
    """Utilities for certificate operations in the MAVIS demo."""

    @staticmethod
    def calculate_cert_length(username: str, device_name: str) -> int:
        """Calculate the total certificate length."""
        username_bytes = len(username.encode("utf-8"))
        device_name_bytes = len(device_name.encode("utf-8"))
        # Fixed fields: B (1) + Q (8) + Q (8) + I (4) + I (4) + B (1) + B (1) = 27 bytes
        fixed_fields_length = struct.calcsize(">BQQII") + 2
        return fixed_fields_length + username_bytes + device_name_bytes

    @staticmethod
    def create_certificate(
        image_id: int,
        user_id: int,
        device_id: int,
        username: str,
        device_name: str,
        timestamp: int = None,
    ) -> DemoCertificate:
        """
        Create a new certificate.

        Args:
            image_id: Unique image identifier
            user_id: User identifier (can be hash of UUID)
            device_id: Device identifier (can be hash of UUID)
            username: Username
            device_name: Device name (truncated to 20 chars)
            timestamp: Unix timestamp (defaults to current time)

        Returns:
            DemoCertificate object
        """
        if timestamp is None:
            timestamp = int(time.time())

        # Truncate device_name to 20 chars as per original implementation
        device_name = device_name[:20]

        cert_len = CertificateUtils.calculate_cert_length(username, device_name)

        return DemoCertificate(
            cert_len=cert_len,
            timestamp=timestamp,
            image_id=image_id,
            user_id=user_id,
            device_id=device_id,
            username=username,
            device_name=device_name,
        )

    @staticmethod
    def serialize_certificate(cert: DemoCertificate) -> bytes:
        """
        Serialize a certificate to bytes.

        Format:
        - cert_len: 8 bits (unsigned char)
        - timestamp: 64 bits (unsigned long long)
        - image_id: 64 bits (unsigned long long)
        - user_id: 32 bits (unsigned int)
        - device_id: 32 bits (unsigned int)
        - username_length: 8 bits (unsigned char)
        - username: variable length string
        - device_name_length: 8 bits (unsigned char)
        - device_name: variable length string
        """
        username_bytes = cert.username.encode("utf-8")
        device_name_bytes = cert.device_name.encode("utf-8")

        header = struct.pack(
            ">BQQII",
            int(cert.cert_len & 0xFF),
            int(cert.timestamp & 0xFFFFFFFFFFFFFFFF),
            int(cert.image_id & 0xFFFFFFFFFFFFFFFF),
            int(cert.user_id & 0xFFFFFFFF),
            int(cert.device_id & 0xFFFFFFFF),
        )

        variable_fields = struct.pack(
            f">B{len(username_bytes)}sB{len(device_name_bytes)}s",
            len(username_bytes),
            username_bytes,
            len(device_name_bytes),
            device_name_bytes,
        )

        return header + variable_fields

    @staticmethod
    def deserialize_certificate(data: bytes) -> Tuple[DemoCertificate, int]:
        """
        Deserialize bytes into a certificate.

        Returns:
            Tuple of (certificate, bytes_consumed)
        """
        fixed_format = ">BQQII"
        fixed_size = struct.calcsize(fixed_format)

        cert_len, timestamp, image_id, user_id, device_id = struct.unpack(
            fixed_format, data[:fixed_size]
        )

        username_length = data[fixed_size]
        username_start = fixed_size + 1
        username_end = username_start + username_length
        username = data[username_start:username_end].decode("utf-8")

        device_name_length = data[username_end]
        device_name_start = username_end + 1
        device_name_end = device_name_start + device_name_length
        device_name = data[device_name_start:device_name_end].decode("utf-8")

        certificate = DemoCertificate(
            cert_len=cert_len,
            timestamp=timestamp,
            image_id=image_id,
            user_id=user_id,
            device_id=device_id,
            username=username,
            device_name=device_name,
        )

        return certificate, device_name_end

    @staticmethod
    def certificate_to_hex(cert: DemoCertificate) -> str:
        """Convert certificate to hex string."""
        return CertificateUtils.serialize_certificate(cert).hex()

    @staticmethod
    def certificate_from_hex(hex_string: str) -> DemoCertificate:
        """Create certificate from hex string."""
        data = bytes.fromhex(hex_string)
        cert, _ = CertificateUtils.deserialize_certificate(data)
        return cert

    @staticmethod
    def hash_certificate(cert: DemoCertificate) -> str:
        """
        Generate SHA-256 hash of a certificate.

        The hash is computed from the serialized certificate bytes.

        Args:
            cert: DemoCertificate object

        Returns:
            Hex string of the SHA-256 hash
        """
        serialized = CertificateUtils.serialize_certificate(cert)
        return hashlib.sha256(serialized).hexdigest()

    @staticmethod
    def hash_certificate_hex(cert_hex: str) -> str:
        """
        Generate SHA-256 hash from certificate hex string.

        Args:
            cert_hex: Hex-encoded certificate string

        Returns:
            Hex string of the SHA-256 hash
        """
        data = bytes.fromhex(cert_hex)
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def uuid_to_int(uuid_str: str) -> int:
        """
        Convert a UUID string to an integer (for use in certificate fields).

        Uses hash to ensure it fits in 32 bits.

        Args:
            uuid_str: UUID string

        Returns:
            32-bit integer derived from the UUID
        """
        # Hash the UUID and take first 4 bytes
        hash_bytes = hashlib.sha256(uuid_str.encode()).digest()[:4]
        return struct.unpack(">I", hash_bytes)[0]
