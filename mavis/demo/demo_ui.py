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
MAVIS Demo UI

A Gradio-based demo interface showcasing the complete MAVIS workflow:
- Tab 1: Capture & Certify - Device registration, image capture, and certification
- Tab 2: Verify Image - Image verification with EXIF and QR extraction
"""

import gradio as gr
import tempfile
import os
from typing import Optional, Tuple
from PIL import Image

from .capture_workflow import CaptureWorkflow

# Global workflow instance (maintains state across Gradio callbacks)
workflow = CaptureWorkflow()


# ============================================================================
# Capture Tab Callbacks
# ============================================================================


def register_device_callback(
    username: str, device_name: str
) -> Tuple[str, str, str, str]:
    """
    Handle device registration.

    Returns:
        Tuple of (status_message, device_id, user_id, public_key_preview)
    """
    if not username or not username.strip():
        return "❌ Please enter a username", "", "", ""

    if not device_name or not device_name.strip():
        device_name = "iPhone 15 Pro"

    success, message, device_id, user_id, pub_key_preview = workflow.register_device(
        username=username.strip(), device_name=device_name.strip()
    )

    if success:
        return (
            message,
            device_id or "",
            user_id or "",
            pub_key_preview or "",
        )
    else:
        return message, "", "", ""


def process_image_callback(
    image: Optional[Image.Image],
) -> Tuple[Optional[Image.Image], str, str, Optional[str]]:
    """
    Handle image capture and certification.

    Returns:
        Tuple of (output_image, workflow_log, certificate_details, download_path)
    """
    if image is None:
        return None, "❌ Please upload or capture an image first.", "", None

    if not workflow.is_device_registered:
        return (
            None,
            "❌ Please register a device first (Step 1).",
            "",
            None,
        )

    # Process the image
    result = workflow.process_image(image)

    # Format workflow log
    workflow_log = "\n".join(result.steps)

    # Format certificate details
    if result.certificate:
        cert_dict = result.certificate.to_dict()
        cert_details = (
            f"📜 Certificate Details\n"
            f"{'='*40}\n"
            f"Image ID: {cert_dict['image_id']}\n"
            f"Timestamp: {cert_dict['timestamp_readable']}\n"
            f"Username: {cert_dict['username']}\n"
            f"Device: {cert_dict['device_name']}\n"
            f"User ID: {cert_dict['user_id']}\n"
            f"Device ID: {cert_dict['device_id']}\n"
            f"{'='*40}\n"
            f"Certificate Hash:\n{result.cert_hash}"
        )
    else:
        cert_details = "No certificate generated"

    # Save output image for download (preserving EXIF)
    download_path = None
    if result.output_image:
        temp_dir = tempfile.mkdtemp()
        download_path = os.path.join(temp_dir, "certified_image.jpg")
        # Preserve EXIF data when saving
        exif_data = result.output_image.info.get("exif")
        save_kwargs = {"format": "JPEG", "quality": 95}
        if exif_data:
            save_kwargs["exif"] = exif_data
        result.output_image.save(download_path, **save_kwargs)

    return result.output_image, workflow_log, cert_details, download_path


def get_device_status() -> str:
    """Get current device registration status."""
    if workflow.is_device_registered:
        info = workflow.get_device_info()
        if info:
            return (
                f"✅ Device Registered\n"
                f"User: {info['username']}\n"
                f"Device: {info['device_name']}"
            )
    return "⚠️ No device registered"


# ============================================================================
# Verification Tab Callbacks
# ============================================================================


def verify_image_callback(
    image: Optional[Image.Image],
) -> Tuple[str, str, Optional[Image.Image], str]:
    """
    Handle image verification.

    Returns:
        Tuple of (verification_status, certificate_details, original_image, workflow_log)
    """
    from .exif_utils import ExifUtils
    from .crypto import CryptoUtils
    from .certificate_utils import CertificateUtils
    from .database import DemoDatabase
    from mavis.algorithms.qr_steganography import QRCodeSteganography

    if image is None:
        return "❌ Please upload an image to verify.", "", None, ""

    db = DemoDatabase()
    steganography = QRCodeSteganography()
    steps = []

    # Step 1: Try to extract certificate from EXIF
    steps.append("🔍 Step 1: Checking for EXIF certificate data...")
    encrypted_cert, exif_cert_hash, exif_error = (
        ExifUtils.extract_certificate_from_exif(image)
    )

    has_exif = encrypted_cert is not None
    if has_exif and exif_cert_hash:
        steps.append("   ✅ Found MAVIS certificate in EXIF!")
        steps.append(f"   Certificate hash from EXIF: {exif_cert_hash[:32]}...")
    else:
        steps.append(f"   ⚠️ No EXIF certificate: {exif_error}")
        steps.append("   Will attempt QR-based verification...")

    # Step 2: Extract QR code from image pixels
    steps.append("\n📱 Step 2: Extracting QR code from image pixels...")
    extracted_payload, extract_status = steganography.extract(image)

    has_qr = extracted_payload is not None
    qr_cert_hash = None
    if has_qr:
        qr_cert_hash = extracted_payload.decode("utf-8").strip()
        steps.append("   ✅ QR code extracted successfully!")
        steps.append(f"   Certificate hash from QR: {qr_cert_hash[:32]}...")
    else:
        steps.append(f"   ❌ QR extraction failed: {extract_status}")

    # Step 3: Verification logic
    steps.append("\n🔐 Step 3: Verifying certificate...")

    verification_status = ""
    cert_details = ""
    original_image = None

    if has_exif and encrypted_cert:
        # Primary path: Decrypt and verify EXIF certificate
        steps.append("   Using EXIF-based verification (primary path)...")

        try:
            # Decrypt the certificate
            decrypted_hex = CryptoUtils.decrypt_certificate(encrypted_cert)
            if decrypted_hex is None:
                raise ValueError("Failed to decrypt certificate")
            certificate = CertificateUtils.certificate_from_hex(decrypted_hex)

            # Hash the decrypted certificate
            computed_hash = CertificateUtils.hash_certificate(certificate)
            steps.append(f"   Computed certificate hash: {computed_hash[:32]}...")

            # Compare with QR hash if available
            if has_qr and qr_cert_hash:
                if computed_hash == qr_cert_hash:
                    steps.append("   ✅ Certificate hash matches QR code!")
                    verification_status = "✅ VERIFIED - Image is authentic!"
                else:
                    steps.append("   ❌ Certificate hash does NOT match QR code!")
                    verification_status = (
                        "❌ VERIFICATION FAILED - Hashes don't match"
                    )
            else:
                # No QR, but we have EXIF - partial verification
                steps.append("   ⚠️ No QR code for comparison, using EXIF data only")
                verification_status = (
                    "⚠️ PARTIAL - Certificate found but no QR verification"
                )

            # Format certificate details
            cert_dict = certificate.to_dict()
            cert_details = (
                f"📜 Certificate Details\n"
                f"{'='*40}\n"
                f"Image ID: {cert_dict['image_id']}\n"
                f"Timestamp: {cert_dict['timestamp_readable']}\n"
                f"Username: {cert_dict['username']}\n"
                f"Device: {cert_dict['device_name']}\n"
                f"User ID: {cert_dict['user_id']}\n"
                f"Device ID: {cert_dict['device_id']}\n"
                f"{'='*40}\n"
                f"Certificate Hash:\n{computed_hash}"
            )

        except Exception as e:
            steps.append(f"   ❌ Failed to decrypt/parse certificate: {e}")
            verification_status = (
                "❌ VERIFICATION FAILED - Certificate decryption error"
            )

    elif has_qr and qr_cert_hash:
        # Fallback path: WhatsApp scenario - lookup by QR hash
        steps.append("   Using QR-based database lookup (WhatsApp scenario)...")

        stored_cert = db.get_certificate(qr_cert_hash)
        stored_image = db.get_image(qr_cert_hash)

        if stored_cert:
            steps.append("   ✅ Certificate found in database!")

            try:
                decrypted_hex = CryptoUtils.decrypt_certificate(
                    stored_cert.encrypted_certificate
                )
                if decrypted_hex is None:
                    raise ValueError("Failed to decrypt stored certificate")
                certificate = CertificateUtils.certificate_from_hex(decrypted_hex)

                cert_dict = certificate.to_dict()
                cert_details = (
                    f"📜 Certificate Details (from database)\n"
                    f"{'='*40}\n"
                    f"Image ID: {cert_dict['image_id']}\n"
                    f"Timestamp: {cert_dict['timestamp_readable']}\n"
                    f"Username: {cert_dict['username']}\n"
                    f"Device: {cert_dict['device_name']}\n"
                    f"{'='*40}\n"
                    f"Certificate Hash:\n{qr_cert_hash}"
                )

                verification_status = (
                    "✅ VERIFIED via Database Lookup\n"
                    "(EXIF was stripped, verified using embedded QR code)"
                )

                if stored_image:
                    steps.append("   ✅ Original image retrieved from database!")
                    original_image = stored_image
                else:
                    steps.append("   ⚠️ Original image not found in database")

            except Exception as e:
                steps.append(f"   ❌ Failed to parse stored certificate: {e}")
                verification_status = (
                    "❌ VERIFICATION FAILED - Certificate parse error"
                )
        else:
            steps.append("   ❌ Certificate not found in database")
            verification_status = "❌ UNKNOWN - Certificate not in database"

    else:
        # No EXIF and no QR
        steps.append("   ❌ No certificate data found in image")
        verification_status = "❌ UNKNOWN - No MAVIS certificate found"

    steps.append("\n" + "=" * 50)
    steps.append(verification_status)

    return verification_status, cert_details, original_image, "\n".join(steps)


def simulate_whatsapp_callback(
    image: Optional[Image.Image],
) -> Optional[Image.Image]:
    """
    Simulate WhatsApp metadata stripping.

    Returns:
        Image with EXIF data stripped
    """
    from .exif_utils import ExifUtils

    if image is None:
        return None

    return ExifUtils.strip_exif(image)


# ============================================================================
# Build Gradio UI
# ============================================================================


def create_demo() -> gr.Blocks:
    """Create the main Gradio demo interface."""

    with gr.Blocks(
        title="MAVIS Demo - Image Provenance System",
    ) as demo:
        gr.Markdown(
            """
            # 📷 MAVIS Demo - Image Provenance System

            This demo showcases the complete MAVIS workflow for image authentication:
            - **Capture & Certify**: Register a device, capture/upload an image, and create a tamper-proof certificate
            - **Verify Image**: Verify any image's authenticity using EXIF metadata or embedded QR code

            ---
            """
        )

        with gr.Tabs():
            # ================================================================
            # Tab 1: Capture & Certify
            # ================================================================
            with gr.TabItem("📸 Capture & Certify"):
                gr.Markdown("### Step 1: Device Registration")
                gr.Markdown(
                    "*Emulates iPhone Secure Enclave - generates a hardware-backed key pair*"
                )

                with gr.Row():
                    with gr.Column(scale=1):
                        username_input = gr.Textbox(
                            label="Username",
                            placeholder="Enter your username",
                            info="Your identity for certificate creation",
                        )
                        device_name_input = gr.Textbox(
                            label="Device Name",
                            value="iPhone 15 Pro",
                            info="Device model (emulated)",
                        )
                        register_btn = gr.Button(
                            "🔐 Register Device", variant="primary"
                        )

                    with gr.Column(scale=1):
                        device_status = gr.Textbox(
                            label="Registration Status",
                            value=get_device_status(),
                            interactive=False,
                            lines=3,
                        )
                        device_id_display = gr.Textbox(
                            label="Device ID", interactive=False
                        )
                        user_id_display = gr.Textbox(
                            label="User ID", interactive=False
                        )
                        pubkey_display = gr.Textbox(
                            label="Public Key (preview)", interactive=False
                        )

                gr.Markdown("---")
                gr.Markdown("### Step 2: Capture & Certify Image")

                with gr.Row():
                    with gr.Column(scale=1):
                        input_image = gr.Image(
                            label="Upload or Capture Image",
                            type="pil",
                            sources=["upload", "webcam"],
                        )
                        process_btn = gr.Button(
                            "🔏 Sign & Certify Image", variant="primary"
                        )

                    with gr.Column(scale=1):
                        output_image = gr.Image(
                            label="Certified Image (with embedded certificate)",
                            type="pil",
                        )
                        download_file = gr.File(
                            label="Download Certified Image",
                        )

                with gr.Row():
                    with gr.Column(scale=1):
                        workflow_log = gr.Textbox(
                            label="Workflow Log",
                            lines=15,
                            interactive=False,
                        )
                    with gr.Column(scale=1):
                        cert_details = gr.Textbox(
                            label="Certificate Details",
                            lines=15,
                            interactive=False,
                        )

                # Wire up callbacks
                register_btn.click(
                    fn=register_device_callback,
                    inputs=[username_input, device_name_input],
                    outputs=[
                        device_status,
                        device_id_display,
                        user_id_display,
                        pubkey_display,
                    ],
                )

                process_btn.click(
                    fn=process_image_callback,
                    inputs=[input_image],
                    outputs=[
                        output_image,
                        workflow_log,
                        cert_details,
                        download_file,
                    ],
                )

            # ================================================================
            # Tab 2: Verify Image
            # ================================================================
            with gr.TabItem("🔍 Verify Image"):
                gr.Markdown("### Image Verification")
                gr.Markdown(
                    """
                    Upload an image to verify its authenticity.
                    - **Primary path**: Extracts certificate from EXIF and verifies against embedded QR code
                    - **WhatsApp scenario**: If EXIF is stripped, uses QR code to lookup certificate in database
                    """
                )

                with gr.Row():
                    with gr.Column(scale=1):
                        verify_input = gr.Image(
                            label="Image to Verify",
                            type="pil",
                            sources=["upload"],
                        )
                        with gr.Row():
                            verify_btn = gr.Button(
                                "🔍 Verify Image", variant="primary"
                            )
                            whatsapp_btn = gr.Button(
                                "📱 Simulate WhatsApp (strip EXIF)",
                                variant="secondary",
                            )

                    with gr.Column(scale=1):
                        verification_status = gr.Textbox(
                            label="Verification Status",
                            lines=3,
                            interactive=False,
                        )
                        original_image_display = gr.Image(
                            label="Original Image (from database, if available)",
                            type="pil",
                        )

                with gr.Row():
                    with gr.Column(scale=1):
                        verify_log = gr.Textbox(
                            label="Verification Log",
                            lines=15,
                            interactive=False,
                        )
                    with gr.Column(scale=1):
                        verify_cert_details = gr.Textbox(
                            label="Certificate Details",
                            lines=15,
                            interactive=False,
                        )

                # Wire up callbacks
                verify_btn.click(
                    fn=verify_image_callback,
                    inputs=[verify_input],
                    outputs=[
                        verification_status,
                        verify_cert_details,
                        original_image_display,
                        verify_log,
                    ],
                )

                whatsapp_btn.click(
                    fn=simulate_whatsapp_callback,
                    inputs=[verify_input],
                    outputs=[verify_input],
                )

        gr.Markdown(
            """
            ---
            ### About MAVIS

            MAVIS (Media Authentication and Verification through Integrated Steganography)
            is a system for establishing image provenance using:

            - **Hardware-backed signing**: Emulates iPhone Secure Enclave for tamper-proof signatures
            - **Digital certificates**: Creates verifiable records of image origin
            - **Steganographic watermarking**: Embeds certificate hash as QR code in image pixels
            - **EXIF embedding**: Stores encrypted certificate in image metadata
            - **Database fallback**: Enables verification even when metadata is stripped

            *This is a demonstration of the concept - not production-ready code.*
            """
        )

    return demo


# ============================================================================
# Launch Functions
# ============================================================================


def launch_demo(share: bool = False, debug: bool = False):
    """
    Launch the MAVIS demo.

    Args:
        share: Whether to create a public Gradio link
        debug: Whether to enable debug mode
    """
    demo = create_demo()
    demo.launch(share=share, debug=debug)


if __name__ == "__main__":
    launch_demo(debug=True)
