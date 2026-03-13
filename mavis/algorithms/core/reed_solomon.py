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
from scipy.fftpack import dct as scipy_dct, idct as scipy_idct
import cv2 # needs libzbar
import reedsolo as rs
from PIL import Image
from typing import Tuple, Optional, List

"""
This module provides core functions for embedding and extracting data
into and from images using DCT-based steganography with Reed-Solomon
error correction. It includes helper functions for image conversion,
binary manipulation, and the embed/extract algorithms.
"""


# --- Helper Functions ---


def pil_to_cv2(pil_image: Image.Image) -> np.ndarray:
    """Convert PIL Image to OpenCV BGR format."""
    pil_image_rgb = pil_image.convert("RGB")
    return cv2.cvtColor(np.array(pil_image_rgb), cv2.COLOR_RGB2BGR)


def cv2_to_pil(cv2_image: np.ndarray) -> Image.Image:
    """Convert OpenCV BGR format to PIL Image."""
    cv2_image_rgb = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(cv2_image_rgb)


def resize_image_max_dimension(
    img: np.ndarray, max_dimension: int = 1024
) -> np.ndarray:
    """Resize image if its max dimension exceeds the specified limit."""
    height, width = img.shape[:2]
    if max(height, width) > max_dimension:
        scale_factor = max_dimension / max(height, width)
        if scale_factor < 1:
            new_width = max(1, int(width * scale_factor))
            new_height = max(1, int(height * scale_factor))
            resized_img = cv2.resize(
                img, (new_width, new_height), interpolation=cv2.INTER_AREA
            )
            return resized_img
    return img


def binary_string_to_byte_array(binary_string: str) -> bytes:
    """Convert a binary string to a byte array."""
    if len(binary_string) % 8 != 0:
        padding = (8 - len(binary_string) % 8) % 8
        binary_string = "0" * padding + binary_string

    if not binary_string:
        return b""

    try:
        integer_value = int(binary_string, 2)
    except ValueError:
        raise ValueError("Invalid character in binary string.")

    num_bytes = len(binary_string) // 8
    try:
        byte_array = integer_value.to_bytes(num_bytes, byteorder="big")
    except OverflowError:
        if integer_value == 0 and num_bytes == 0:
            return b""
        raise ValueError(
            "Error converting integer to bytes, possibly due to invalid binary string or length calculation."
        )
    return byte_array


# --- Core Embedding Function ---


def embed_reed_solomon_dct(
    img_cv: np.ndarray,
    payload: bytes,
    strength: int,
    max_dimension: int,
    len_ecc_nsym: int,
    payload_ecc_factor: float,
) -> Tuple[Optional[np.ndarray], List[str]]:
    """
    Embeds payload into an image using DCT-based steganography with Reed-Solomon ECC.

    Args:
        img_cv: Input image in OpenCV BGR format.
        payload: The data to embed.
        strength: Embedding strength for DCT coefficient modification.
        max_dimension: Maximum image dimension (for resizing).
        len_ecc_nsym: Number of ECC symbols for payload length.
        payload_ecc_factor: Factor to calculate payload ECC symbols.

    Returns:
        Tuple containing:
            - Modified image in OpenCV BGR format, or None on failure.
            - List of status messages.
    """
    status_msgs = []

    if len(payload) == 0:
        return None, ["Error: Payload is empty."]
    if len(payload) > 200:
        status_msgs.append(
            f"Warning: Payload length {len(payload)} is large. Consider reducing."
        )

    # Resize before processing
    h_orig, w_orig = img_cv.shape[:2]
    img_cv_resized = resize_image_max_dimension(img_cv, max_dimension=max_dimension)
    h_resized, w_resized = img_cv_resized.shape[:2]
    if (h_orig, w_orig) != (h_resized, w_resized):
        status_msgs.append(
            f"Image resized from {w_orig}x{h_orig} to {w_resized}x{h_resized}"
        )

    try:
        ycrcb_img = cv2.cvtColor(img_cv_resized, cv2.COLOR_BGR2YCrCb)
        y_channel = ycrcb_img[:, :, 0].astype(float)
    except cv2.error as e:
        return None, [f"OpenCV error during color conversion: {e}"]

    payload_len = len(payload)
    payload_len_bytes = payload_len.to_bytes(2, byteorder="big")

    # Validate ECC parameters
    if not (0 < len_ecc_nsym < 256 - len(payload_len_bytes)):
        return None, [
            f"Invalid length_ecc_symbols: {len_ecc_nsym}. Must be >0 and < {256-len(payload_len_bytes)}."
        ]

    payload_ecc_nsym = int(payload_len * payload_ecc_factor)
    if not (0 < payload_ecc_nsym < 256 - payload_len):
        return None, [
            f"Invalid payload_ecc_symbols derived: {payload_ecc_nsym}. Must be >0 and < {256-payload_len}."
        ]

    rsc_len = rs.RSCodec(len_ecc_nsym)
    rsc_payload = rs.RSCodec(payload_ecc_nsym)

    try:
        length_bytes_encoded = rsc_len.encode(payload_len_bytes)
        payload_encoded = rsc_payload.encode(payload)
    except (rs.ReedSolomonError, ValueError) as e:
        return None, [f"Reed-Solomon encoding error: {e}"]

    combined_payload_encoded = length_bytes_encoded + payload_encoded
    all_bits_to_embed = "".join(
        format(byte, "08b") for byte in combined_payload_encoded
    )
    status_msgs.append(
        f"Payload: {payload_len}B, Length ECC: {len_ecc_nsym} sym, Payload ECC: {payload_ecc_nsym} sym."
    )
    status_msgs.append(f"Total bits to embed: {len(all_bits_to_embed)}")

    height, width = y_channel.shape
    block_size = 8

    num_blocks_h = height // block_size
    num_blocks_w = width // block_size
    capacity_bits = num_blocks_h * num_blocks_w

    if len(all_bits_to_embed) > capacity_bits:
        return None, [
            f"Error: Not enough blocks in image ({capacity_bits} bits) to store payload ({len(all_bits_to_embed)} bits)."
        ]

    y_channel_modified = y_channel.copy()
    bit_idx = 0
    effective_strength = max(strength, 1)  # Ensure strength is not zero

    for i in range(0, num_blocks_h * block_size, block_size):
        for j in range(0, num_blocks_w * block_size, block_size):
            if bit_idx >= len(all_bits_to_embed):
                break

            block = y_channel_modified[i : i + block_size, j : j + block_size]
            dct_block = scipy_dct(scipy_dct(block.T, norm="ortho").T, norm="ortho")

            if all_bits_to_embed[bit_idx] == "1":
                dct_block[4, 3] = (
                    np.floor(dct_block[4, 3] / effective_strength)
                    * effective_strength
                    + effective_strength * 0.75
                )
            else:
                dct_block[4, 3] = (
                    np.floor(dct_block[4, 3] / effective_strength)
                    * effective_strength
                    + effective_strength * 0.25
                )
            bit_idx += 1

            modified_block = scipy_idct(
                scipy_idct(dct_block.T, norm="ortho").T, norm="ortho"
            )
            y_channel_modified[i : i + block_size, j : j + block_size] = (
                modified_block
            )
        if bit_idx >= len(all_bits_to_embed):
            break

    y_channel_modified = np.clip(y_channel_modified, 0, 255)

    ycrcb_img_modified = ycrcb_img.copy()
    ycrcb_img_modified[:height, :width, 0] = y_channel_modified.astype(np.uint8)

    try:
        embedded_img_cv = cv2.cvtColor(ycrcb_img_modified, cv2.COLOR_YCrCb2BGR)
    except cv2.error as e:
        return None, [f"OpenCV error during final color conversion: {e}"]

    status_msgs.append(f"Successfully embedded {bit_idx} bits.")
    return embedded_img_cv, status_msgs


# --- Core Extraction Function ---


def extract_reed_solomon_dct(
    img_cv: np.ndarray,
    strength: int,
    len_ecc_nsym: int,
    payload_ecc_factor: float,
) -> Tuple[Optional[bytes], List[str]]:
    """
    Extracts payload from an image using DCT-based steganography with Reed-Solomon ECC.

    Args:
        img_cv: Input image in OpenCV BGR format.
        strength: Embedding strength used during embedding.
        len_ecc_nsym: Number of ECC symbols for payload length.
        payload_ecc_factor: Factor to calculate payload ECC symbols.

    Returns:
        Tuple containing:
            - Extracted payload bytes, or None on failure.
            - List of status messages.
    """
    status_msgs = []

    try:
        ycrcb_img = cv2.cvtColor(img_cv, cv2.COLOR_BGR2YCrCb)
        y_channel = ycrcb_img[:, :, 0].astype(float)
    except cv2.error as e:
        return None, [f"OpenCV error during color conversion: {e}"]

    height, width = y_channel.shape
    block_size = 8

    num_blocks_h = height // block_size
    num_blocks_w = width // block_size

    extracted_bits_list = []
    effective_strength = max(strength, 1)

    for i in range(0, num_blocks_h * block_size, block_size):
        for j in range(0, num_blocks_w * block_size, block_size):
            block = y_channel[i : i + block_size, j : j + block_size]
            dct_block = scipy_dct(scipy_dct(block.T, norm="ortho").T, norm="ortho")
            coef_val = dct_block[4, 3]
            quantized_base = (
                np.floor(coef_val / effective_strength) * effective_strength
            )
            offset_part = coef_val - quantized_base
            extracted_bits_list.append(
                "1" if offset_part > (effective_strength * 0.5) else "0"
            )

    extracted_bits_str = "".join(extracted_bits_list)
    status_msgs.append(f"Extracted {len(extracted_bits_str)} raw bits.")

    # Decode length
    len_field_bytes = (
        len("".join(format(b, "08b") for b in (0).to_bytes(2, "big")))
        + len_ecc_nsym * 8
    )

    if len(extracted_bits_str) < len_field_bytes:
        return None, [
            f"Error: Not enough bits extracted ({len(extracted_bits_str)}) to decode length field (need ~{len_field_bytes})."
        ]

    rsc_len = rs.RSCodec(len_ecc_nsym)
    encoded_len_bits = extracted_bits_str[:len_field_bytes]

    try:
        encoded_len_bytes_arr = binary_string_to_byte_array(encoded_len_bits)
    except ValueError as e:
        return None, [
            f"Error converting length bits to bytes: {e}. Bits: '{encoded_len_bits[:64]}...'"
        ]

    try:
        decoded_len_bytes_with_ecc = rsc_len.decode(encoded_len_bytes_arr)
        decoded_len_bytes = decoded_len_bytes_with_ecc[0]
        actual_payload_len = int.from_bytes(decoded_len_bytes, byteorder="big")
        status_msgs.append(f"Decoded payload length: {actual_payload_len} bytes.")
    except (rs.ReedSolomonError, ValueError, TypeError, IndexError) as e:
        return None, [
            f"Error decoding payload length: {e}. Raw length bytes: {encoded_len_bytes_arr.hex() if isinstance(encoded_len_bytes_arr, bytes) else 'N/A'}"
        ]

    if not (0 < actual_payload_len < 10000):
        return None, [
            f"Error: Decoded payload length {actual_payload_len} seems invalid."
        ]

    # Decode payload
    payload_ecc_nsym = int(actual_payload_len * payload_ecc_factor)
    if not (0 < payload_ecc_nsym < 256 - actual_payload_len):
        return None, [
            f"Error: Invalid payload_ecc_symbols for decoded length: {payload_ecc_nsym} (len={actual_payload_len})."
        ]

    rsc_payload = rs.RSCodec(payload_ecc_nsym)

    encoded_payload_num_bytes = actual_payload_len + payload_ecc_nsym
    encoded_payload_bits_len = encoded_payload_num_bytes * 8

    payload_data_start_bit = len_field_bytes
    payload_data_end_bit = payload_data_start_bit + encoded_payload_bits_len

    if len(extracted_bits_str) < payload_data_end_bit:
        return None, [
            f"Error: Not enough bits for payload data. Extracted: {len(extracted_bits_str)}, Needed up to: {payload_data_end_bit}"
        ]

    encoded_payload_bits = extracted_bits_str[
        payload_data_start_bit:payload_data_end_bit
    ]

    try:
        encoded_payload_bytes_arr = binary_string_to_byte_array(encoded_payload_bits)
    except ValueError as e:
        return None, [
            f"Error converting payload bits to bytes: {e}. Bits: '{encoded_payload_bits[:64]}...'"
        ]

    try:
        decoded_payload_with_ecc = rsc_payload.decode(encoded_payload_bytes_arr)
        final_payload = decoded_payload_with_ecc[0]

        if len(final_payload) != actual_payload_len:
            status_msgs.append(
                f"Warning: Final payload length {len(final_payload)} does not match decoded length {actual_payload_len}."
            )

        status_msgs.append("Payload extracted successfully.")
        final_payload_bytes = (
            bytes(final_payload)
            if not isinstance(final_payload, bytes)
            else final_payload
        )
        return final_payload_bytes, status_msgs
    except (rs.ReedSolomonError, ValueError, TypeError, IndexError) as e:
        return None, [
            f"Error decoding payload: {e}. Raw payload bytes: {encoded_payload_bytes_arr.hex() if isinstance(encoded_payload_bytes_arr, bytes) else 'N/A'}"
        ]
    except Exception as e:
        return None, [f"Unexpected error during payload decoding: {e}"]
