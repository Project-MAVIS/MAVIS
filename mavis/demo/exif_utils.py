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
EXIF Utilities for MAVIS Demo

Provides utilities for:
- Embedding encrypted certificate in EXIF UserComment field
- Extracting certificate from EXIF
- Handling images without EXIF (WhatsApp scenario)
"""

import json
from typing import Optional, Tuple
from io import BytesIO

from PIL import Image
import piexif


# MAVIS-specific EXIF marker
MAVIS_MARKER = "MAVIS_CERT:"


class ExifUtils:
    """Utilities for EXIF operations in the MAVIS demo."""

    @staticmethod
    def embed_certificate_in_exif(
        image: Image.Image,
        encrypted_certificate: str,
        cert_hash: str,
    ) -> Image.Image:
        """
        Embed encrypted certificate data in image EXIF.

        The certificate is stored in the UserComment field with a MAVIS marker.

        Args:
            image: PIL Image object
            encrypted_certificate: Base64-encoded encrypted certificate
            cert_hash: Hash of the certificate (for reference)

        Returns:
            New PIL Image with embedded EXIF data
        """
        # Create MAVIS metadata structure
        mavis_data = {
            "marker": "MAVIS",
            "version": "1.0",
            "cert_hash": cert_hash,
            "encrypted_cert": encrypted_certificate,
        }

        # Convert to JSON string
        metadata_json = json.dumps(mavis_data)

        # Create UserComment with MAVIS marker
        user_comment = f"{MAVIS_MARKER}{metadata_json}"

        # Build EXIF data
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        # UserComment format requires specific encoding
        # Using ASCII charset identifier followed by the data
        user_comment_bytes = b"ASCII\x00\x00\x00" + user_comment.encode("utf-8")
        exif_dict["Exif"][piexif.ExifIFD.UserComment] = user_comment_bytes

        # Add software tag to identify MAVIS
        exif_dict["0th"][piexif.ImageIFD.Software] = "MAVIS v1.0"

        # Dump EXIF to bytes
        exif_bytes = piexif.dump(exif_dict)

        # Save image with new EXIF
        output = BytesIO()

        # Convert to RGB if necessary (JPEG doesn't support RGBA)
        if image.mode == "RGBA":
            image = image.convert("RGB")

        image.save(output, format="JPEG", exif=exif_bytes, quality=95)
        output.seek(0)

        return Image.open(output)

    @staticmethod
    def extract_certificate_from_exif(
        image: Image.Image,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract encrypted certificate from image EXIF.

        Args:
            image: PIL Image object

        Returns:
            Tuple of (encrypted_certificate, cert_hash, error_message)
            If extraction fails, returns (None, None, error_message)
        """
        try:
            # Try to get EXIF data
            exif_data = image.getexif()

            if not exif_data:
                return None, None, "No EXIF data found in image"

            # Look for UserComment
            if piexif.ExifIFD.UserComment not in exif_data:
                return None, None, "No UserComment field in EXIF"

            user_comment_raw = exif_data[piexif.ExifIFD.UserComment]

            # Handle bytes or string
            if isinstance(user_comment_raw, bytes):
                # Skip charset identifier (first 8 bytes for ASCII)
                if user_comment_raw.startswith(b"ASCII\x00\x00\x00"):
                    user_comment = user_comment_raw[8:].decode("utf-8")
                else:
                    user_comment = user_comment_raw.decode("utf-8", errors="ignore")
            else:
                user_comment = str(user_comment_raw)

            # Check for MAVIS marker
            if not user_comment.startswith(MAVIS_MARKER):
                return None, None, "No MAVIS certificate marker found"

            # Parse JSON data
            json_str = user_comment[len(MAVIS_MARKER) :]
            mavis_data = json.loads(json_str)

            encrypted_cert = mavis_data.get("encrypted_cert")
            cert_hash = mavis_data.get("cert_hash")

            if not encrypted_cert:
                return None, None, "No encrypted certificate in MAVIS data"

            return encrypted_cert, cert_hash, None

        except json.JSONDecodeError as e:
            return None, None, f"Failed to parse MAVIS data: {e}"
        except Exception as e:
            return None, None, f"Error extracting EXIF: {e}"

    @staticmethod
    def has_mavis_certificate(image: Image.Image) -> bool:
        """
        Check if an image has a MAVIS certificate embedded.

        Args:
            image: PIL Image object

        Returns:
            True if MAVIS certificate is present, False otherwise
        """
        encrypted_cert, _, _ = ExifUtils.extract_certificate_from_exif(image)
        return encrypted_cert is not None

    @staticmethod
    def strip_exif(image: Image.Image) -> Image.Image:
        """
        Remove all EXIF data from an image.

        This simulates what happens when an image is sent through
        WhatsApp or other services that strip metadata.

        Args:
            image: PIL Image object

        Returns:
            New PIL Image without EXIF data
        """
        # Convert to RGB if necessary
        if image.mode == "RGBA":
            image = image.convert("RGB")

        # Create new image without EXIF by copying pixel data
        data = list(image.getdata())
        image_no_exif = Image.new(image.mode, image.size)
        image_no_exif.putdata(data)

        return image_no_exif
