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
    def _extract_from_exif_bytes(
        exif_bytes: bytes,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Helper to extract certificate from raw EXIF bytes."""
        try:
            exif_dict = piexif.load(exif_bytes)
        except Exception:
            return None, None, "Failed to parse EXIF bytes"

        # Check if Exif IFD exists
        if "Exif" not in exif_dict or not exif_dict["Exif"]:
            return None, None, "No Exif IFD found in image"

        # Look for UserComment in Exif IFD
        if piexif.ExifIFD.UserComment not in exif_dict["Exif"]:
            return None, None, "No UserComment field in EXIF"

        user_comment_raw = exif_dict["Exif"][piexif.ExifIFD.UserComment]

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
            # Method 1: Try to get EXIF from image.info (most reliable for in-memory images)
            exif_info = image.info.get("exif")
            if exif_info and isinstance(exif_info, bytes):
                result = ExifUtils._extract_from_exif_bytes(exif_info)
                if result[0] is not None:
                    return result

            # Method 2: If image has a filename, try loading directly from file
            filename = getattr(image, "filename", None)
            if filename:
                try:
                    exif_dict = piexif.load(filename)
                    if "Exif" in exif_dict and exif_dict["Exif"]:
                        if piexif.ExifIFD.UserComment in exif_dict["Exif"]:
                            # Reconstruct exif bytes and parse
                            exif_bytes = piexif.dump(exif_dict)
                            result = ExifUtils._extract_from_exif_bytes(exif_bytes)
                            if result[0] is not None:
                                return result
                except Exception:
                    pass  # Fall through to next method

            # Method 3: Try saving to bytes and reloading
            # This works when the image was opened from a file with EXIF
            img_bytes = BytesIO()
            img_to_save = image
            if image.mode == "RGBA":
                img_to_save = image.convert("RGB")

            # Try saving with existing EXIF if available
            save_kwargs = {"format": "JPEG", "quality": 95}
            if exif_info:
                save_kwargs["exif"] = exif_info

            img_to_save.save(img_bytes, **save_kwargs)
            img_bytes.seek(0)

            # Try to load EXIF from the saved bytes
            try:
                result = ExifUtils._extract_from_exif_bytes(img_bytes.getvalue())
                if result[0] is not None:
                    return result
            except Exception:
                pass

            return None, None, "No MAVIS certificate found in image EXIF"

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
