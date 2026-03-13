# Copyright (c) 2026 Project MAVIS Authors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, subject to the conditions in the LICENSE file.
#
# See the LICENSE file for more details.

import numpy as np
from PIL import Image
from typing import Tuple, Optional, Dict, Any
from qreader import QReader

from mavis.algorithms.steganography_interface import SteganographyMethod
import mavis.algorithms.core.qr_code as qr_code

# --- Configuration ---
# Default parameters (can be overridden by Gradio inputs)
DEFAULT_ALPHA = 25.0
DEFAULT_WAVELET = "db4"
DEFAULT_SUBBAND = "HL"
DEFAULT_REPETITIONS = 1


class QRCodeSteganography(SteganographyMethod):
    def get_name(self) -> str:
        return "QRCode_DWT_DCT"

    def get_default_settings(self) -> Dict[str, Any]:
        return {
            "alpha": DEFAULT_ALPHA,
            "wavelet_type": DEFAULT_WAVELET,
            "embed_subband": DEFAULT_SUBBAND,
            "repetitions": DEFAULT_REPETITIONS,
        }

    def embed(
        self,
        image: Image.Image,
        payload: bytes,  # utf-8 encoded
        settings: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Image.Image], Any]:
        try:
            config = self.get_default_settings()
            payload_str = payload.decode("utf-8")
            stego_image, status = qr_code.embed_qr_dct_wavelet(
                original_image=image,
                alpha=config["alpha"],
                wavelet_type=config["wavelet_type"],
                embed_subband=config["embed_subband"],
                payload=payload_str,
            )
            return stego_image, status
        except Exception as e:
            return None, f"Error during QR Code embedding: {str(e)}"

    def extract(
        self, image: Image.Image, settings: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[bytes], Any]:
        config = self.get_default_settings()
        if settings:
            config.update(settings)

        # Alpha not strictly needed for sign-based extraction but kept for consistency if method evolves
        alpha_strength = config["alpha"]  # Not used in this extraction logic
        wavelet_type = config["wavelet_type"]
        embed_subband = config["embed_subband"]

        extracted_payload_str = None
        status_list = []
        try:
            # Call the actual extraction function
            extracted_qr_image, extract_status = qr_code.extract_qr_dct_wavelet(
                stego_image=image,
                alpha=alpha_strength,
                wavelet_type=wavelet_type,
                embed_subband=embed_subband,
            )
            status_list.append(extract_status)

            if extracted_qr_image:
                # Decode the extracted QR image
                try:
                    qr_np_array = np.array(extracted_qr_image.convert("L"))
                    reader = QReader()
                    # Use detect_and_decode which returns a tuple of decoded strings
                    decoded_data_tuple = reader.detect_and_decode(image=qr_np_array)

                    # Filter out None values and join potentially multiple decoded results
                    # (usually only one QR code is expected)
                    valid_decoded = [
                        s
                        for s in decoded_data_tuple
                        if s is not None and isinstance(s, str)
                    ]
                    if valid_decoded:
                        extracted_payload_str = "\n---\n".join(valid_decoded).encode(
                            "utf-8"
                        )
                        status_list.append("QR Code decoded successfully.")
                    else:
                        status_list.append(
                            "QR Code detected, but content decoding failed or was empty."
                        )
                except Exception as decode_error:
                    status_list.append(f"Error during QR decoding: {decode_error}")
            else:
                status_list.append("QR Code image extraction failed.")

        except Exception as e:
            status_list.append(f"Error during QR Code extraction process: {str(e)}")

        return extracted_payload_str, "\n".join(status_list)

    # def _debug_save_qr_from_bits(self, bits: List[int], width: int, height: int, filename: str):
    #     """Helper to save a QR image from bits for debugging."""
    #     if not bits or width <= 0 or height <= 0 or len(bits) != width * height:
    #         print(f"Debug save: Invalid parameters for QR reconstruction. Bits: {len(bits)}, W: {width}, H: {height}")
    #         return
    #     try:
    #         qr_matrix_debug = np.array(bits, dtype=np.uint8).reshape((height, width))
    #         # Assuming 1 is black module, 0 is white background for standard QR visualization
    #         qr_image_debug_np = np.where(qr_matrix_debug == 1, 0, 255).astype(np.uint8)
    #         qr_image_debug_pil = Image.fromarray(qr_image_debug_np, mode='L')
    #         qr_image_debug_pil = qr_image_debug_pil.resize((width*10, height*10), Image.NEAREST)
    #         qr_image_debug_pil.save(filename)
    #         print(f"Debug: Saved reconstructed QR image to {filename}")
    #     except Exception as e:
    #         print(f"Debug save error: {e}")
