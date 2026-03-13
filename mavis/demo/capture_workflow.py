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
Capture Workflow for MAVIS Demo

Handles the complete image capture and certification workflow:
1. Device registration (Secure Enclave initialization)
2. Image capture and signing
3. Server-side verification
4. Certificate creation
5. QR code embedding
6. EXIF embedding and storage
"""

from dataclasses import dataclass
from typing import Optional, Tuple, List

from PIL import Image

from .secure_enclave import SecureEnclave
from .crypto import CryptoUtils
from .database import DemoDatabase
from .certificate_utils import CertificateUtils, DemoCertificate
from .exif_utils import ExifUtils
from mavis.algorithms.qr_steganography import QRCodeSteganography


@dataclass
class WorkflowResult:
    """Result of the capture workflow."""

    success: bool
    output_image: Optional[Image.Image]
    certificate: Optional[DemoCertificate]
    cert_hash: str
    steps: List[str]
    error: Optional[str] = None


class CaptureWorkflow:
    """
    Manages the complete capture and certification workflow.

    This class orchestrates the entire process from device registration
    through to final certified image output.
    """

    def __init__(self):
        self.secure_enclave = SecureEnclave()
        self.database = DemoDatabase()
        self.steganography = QRCodeSteganography()
        self._steps: List[str] = []

    def _log_step(self, message: str):
        """Log a workflow step."""
        self._steps.append(message)

    def _clear_steps(self):
        """Clear step log."""
        self._steps = []

    @property
    def is_device_registered(self) -> bool:
        """Check if a device is registered."""
        return self.secure_enclave.is_initialized

    def register_device(
        self, username: str, device_name: str = "iPhone 15 Pro"
    ) -> Tuple[bool, str, Optional[str], Optional[str], Optional[str]]:
        """
        Register a new device with the Secure Enclave.

        Args:
            username: Username for the device owner
            device_name: Name/model of the device

        Returns:
            Tuple of (success, message, device_id, user_id, public_key_preview)
        """
        try:
            # Initialize Secure Enclave (generates key pair)
            device_id, user_id, public_key_pem = (
                self.secure_enclave.initialize_device(
                    username=username, device_name=device_name
                )
            )

            # Register device in database
            self.database.register_device(
                device_id=device_id,
                user_id=user_id,
                username=username,
                device_name=device_name,
                public_key_pem=public_key_pem,
            )

            # Create preview of public key (first and last 20 chars)
            pub_key_str = public_key_pem.decode("utf-8")
            lines = pub_key_str.strip().split("\n")
            # Get the key content (skip header/footer)
            key_content = "".join(lines[1:-1])
            public_key_preview = f"{key_content[:30]}...{key_content[-30:]}"

            return (
                True,
                f"✅ Device registered successfully!\n"
                f"Device ID: {device_id[:8]}...\n"
                f"User ID: {user_id[:8]}...",
                device_id,
                user_id,
                public_key_preview,
            )

        except Exception as e:
            return False, f"❌ Failed to register device: {str(e)}", None, None, None

    def get_device_info(self) -> Optional[dict]:
        """Get current device information."""
        if not self.secure_enclave.is_initialized:
            return None

        return {
            "device_id": self.secure_enclave.device_id,
            "user_id": self.secure_enclave.user_id,
            "username": self.secure_enclave.username,
            "device_name": self.secure_enclave.device_name,
        }

    def process_image(self, image: Image.Image) -> WorkflowResult:
        """
        Process an image through the complete certification workflow.

        Steps:
        1. Hash the image
        2. Sign the hash with Secure Enclave
        3. Verify signature (server-side simulation)
        4. Create certificate
        5. Embed certificate hash as QR code
        6. Embed encrypted certificate in EXIF
        7. Store in database

        Args:
            image: PIL Image to process

        Returns:
            WorkflowResult with output image and certificate details
        """
        self._clear_steps()

        # Validate device is registered
        if not self.secure_enclave.is_initialized:
            return WorkflowResult(
                success=False,
                output_image=None,
                certificate=None,
                cert_hash="",
                steps=["❌ No device registered. Please register a device first."],
                error="Device not registered",
            )

        try:
            return self._execute_workflow(image)
        except Exception as e:
            self._log_step(f"❌ Workflow failed: {str(e)}")
            return WorkflowResult(
                success=False,
                output_image=None,
                certificate=None,
                cert_hash="",
                steps=self._steps,
                error=str(e),
            )

    def _execute_workflow(self, image: Image.Image) -> WorkflowResult:
        """Execute the full certification workflow."""

        # These assertions are safe because we check is_initialized before calling
        assert self.secure_enclave.user_id is not None
        assert self.secure_enclave.device_id is not None
        assert self.secure_enclave.username is not None
        assert self.secure_enclave.device_name is not None

        # Step 1: Hash the image
        self._log_step("📸 Step 1: Computing image hash...")
        image_hash = CryptoUtils.hash_image(image)
        self._log_step(f"   Image hash: {image_hash[:16]}...{image_hash[-16:]}")

        # Step 2: Sign with Secure Enclave
        self._log_step("🔐 Step 2: Signing image with Secure Enclave...")
        signature = self.secure_enclave.sign_image_hash(image_hash)
        self._log_step(f"   Signature: {signature.hex()[:32]}...")

        # Step 3: Server-side verification
        self._log_step("✅ Step 3: Server verifying signature...")
        public_key = self.secure_enclave.get_public_key()
        is_valid = CryptoUtils.verify_image_signature(
            image_hash=image_hash,
            signature=signature,
            public_key_pem=public_key,
        )

        if not is_valid:
            self._log_step("   ❌ Signature verification FAILED!")
            return WorkflowResult(
                success=False,
                output_image=None,
                certificate=None,
                cert_hash="",
                steps=self._steps,
                error="Signature verification failed",
            )
        self._log_step("   ✅ Signature verified successfully!")

        # Step 4: Create certificate
        self._log_step("📜 Step 4: Creating certificate...")
        image_id = self.database.get_next_image_id()
        user_id_int = CertificateUtils.uuid_to_int(self.secure_enclave.user_id)
        device_id_int = CertificateUtils.uuid_to_int(self.secure_enclave.device_id)

        certificate = CertificateUtils.create_certificate(
            image_id=image_id,
            user_id=user_id_int,
            device_id=device_id_int,
            username=self.secure_enclave.username,
            device_name=self.secure_enclave.device_name,
        )
        self._log_step(f"   Certificate created for image #{image_id}")

        # Step 5: Hash the certificate
        self._log_step("🔗 Step 5: Computing certificate hash...")
        cert_hash = CertificateUtils.hash_certificate(certificate)
        self._log_step(f"   Certificate hash: {cert_hash[:16]}...{cert_hash[-16:]}")

        # Step 6: Embed certificate hash as QR code
        self._log_step("📱 Step 6: Embedding certificate hash as QR code...")
        watermarked_image, embed_status = self.steganography.embed(
            image=image,
            payload=cert_hash.encode("utf-8"),
        )

        if watermarked_image is None:
            self._log_step(f"   ❌ QR embedding failed: {embed_status}")
            return WorkflowResult(
                success=False,
                output_image=None,
                certificate=certificate,
                cert_hash=cert_hash,
                steps=self._steps,
                error=f"QR embedding failed: {embed_status}",
            )
        self._log_step("   ✅ QR code embedded successfully!")

        # Step 7: Encrypt certificate and embed in EXIF
        self._log_step("🔒 Step 7: Encrypting certificate and embedding in EXIF...")
        cert_hex = CertificateUtils.certificate_to_hex(certificate)
        encrypted_cert = CryptoUtils.encrypt_certificate(cert_hex)
        self._log_step(
            f"   Encrypted certificate length: {len(encrypted_cert)} chars"
        )

        output_image = ExifUtils.embed_certificate_in_exif(
            image=watermarked_image,
            encrypted_certificate=encrypted_cert,
            cert_hash=cert_hash,
        )
        self._log_step("   ✅ Certificate embedded in EXIF!")

        # Step 8: Store in database
        self._log_step("💾 Step 8: Storing in database...")
        self.database.store_certificate(
            cert_hash=cert_hash,
            encrypted_certificate=encrypted_cert,
            image_id=image_id,
            device_id=self.secure_enclave.device_id,
        )
        self.database.store_image(
            cert_hash=cert_hash,
            image=image,  # Store original image
        )
        self._log_step("   ✅ Certificate and original image stored!")

        self._log_step("")
        self._log_step("🎉 Image certification complete!")

        return WorkflowResult(
            success=True,
            output_image=output_image,
            certificate=certificate,
            cert_hash=cert_hash,
            steps=self._steps,
        )
