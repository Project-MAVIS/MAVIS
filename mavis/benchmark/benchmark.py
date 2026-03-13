# Copyright (c) 2026 Project MAVIS Authors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, subject to the conditions in the LICENSE file.
#
# See the LICENSE file for more details.

import os
import csv
import time
import io
from PIL import Image, ImageFilter, UnidentifiedImageError
import numpy as np
from typing import List, Optional

# Try to import skimage metrics, handle if not available
try:
    from skimage.metrics import peak_signal_noise_ratio
    from skimage.metrics import structural_similarity

    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False
    print(
        "Warning: scikit-image not found. PSNR and SSIM metrics will not be calculated."
    )
    print("Please install it: pip install scikit-image")

from mavis.algorithms.steganography_interface import SteganographyMethod
from mavis.algorithms.qr_steganography import QRCodeSteganography
from mavis.algorithms.rs_steganography import ReedSolomonSteganography

# --- Configuration ---
INPUT_DIR = "input/"
OUTPUT_DIR = "output/"
PAYLOAD_DATA = b"0123456789abcdef0123456789abcdef"  # 32 bytes
CSV_RESULTS_FILE = os.path.join(OUTPUT_DIR, "benchmark_results.csv")


# --- Helper Functions ---
def ensure_dir(directory_path: str):
    os.makedirs(directory_path, exist_ok=True)


def get_image_paths(directory: str) -> List[str]:
    paths = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff")):
                paths.append(os.path.join(root, file))
    return paths


def calculate_psnr(img1_pil: Image.Image, img2_pil: Image.Image) -> Optional[float]:
    if not SKIMAGE_AVAILABLE:
        return None
    try:
        # Ensure images are same size and mode for comparison
        if img1_pil.size != img2_pil.size or img1_pil.mode != img2_pil.mode:
            # Attempt to make them compatible: resize img2 to img1's size, convert both to RGB
            img2_pil_resized = img2_pil.resize(
                img1_pil.size, Image.Resampling.LANCZOS
            )
            img1_rgb = img1_pil.convert("RGB")
            img2_rgb = img2_pil_resized.convert("RGB")
        else:
            img1_rgb = img1_pil.convert("RGB")
            img2_rgb = img2_pil.convert("RGB")

        img1_np = np.array(img1_rgb)
        img2_np = np.array(img2_rgb)

        if img1_np.shape != img2_np.shape:  # Should not happen after resize
            print(
                f"PSNR calc: Shape mismatch after resize {img1_np.shape} vs {img2_np.shape}"
            )
            return None

        return peak_signal_noise_ratio(img1_np, img2_np, data_range=255)  # type: ignore
    except Exception as e:
        print(f"Error calculating PSNR: {e}")
        return None


def calculate_ssim(img1_pil: Image.Image, img2_pil: Image.Image) -> Optional[float]:
    if not SKIMAGE_AVAILABLE:
        return None
    try:
        if img1_pil.size != img2_pil.size or img1_pil.mode != img2_pil.mode:
            img2_pil_resized = img2_pil.resize(
                img1_pil.size, Image.Resampling.LANCZOS
            )
            img1_rgb = img1_pil.convert("L")  # SSIM often on grayscale
            img2_rgb = img2_pil_resized.convert("L")
        else:
            img1_rgb = img1_pil.convert("L")
            img2_rgb = img2_pil.convert("L")

        img1_np = np.array(img1_rgb)
        img2_np = np.array(img2_rgb)

        if img1_np.shape != img2_np.shape:
            print(
                f"SSIM calc: Shape mismatch after resize {img1_np.shape} vs {img2_np.shape}"
            )
            return None

        # For SSIM, win_size might need to be adjusted if images are too small.
        # Default win_size is 7. It must be odd and smaller than image dimensions.
        min_dim = min(img1_np.shape)
        win_size = min(7, min_dim if min_dim % 2 != 0 else min_dim - 1)
        if win_size < 3:  # too small for meaningful ssim
            # print(f"SSIM calc: Image dimension {min_dim} too small for default window size.")
            return None

        return structural_similarity(
            img1_np,
            img2_np,
            data_range=255,
            win_size=win_size,
            channel_axis=None if len(img1_np.shape) == 2 else -1,
        )
    except Exception as e:
        print(f"Error calculating SSIM: {e}")
        return None


# --- Image Attack Functions ---
# Each attack function takes a PIL Image and parameters, returns attacked PIL Image.


def attack_jpeg_compression(
    image: Image.Image, quality: int
) -> Optional[Image.Image]:
    try:
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)
        return Image.open(buffer)
    except Exception as e:
        print(f"Error during JPEG compression attack: {e}")
        return None


def attack_gaussian_blur(image: Image.Image, radius: float) -> Optional[Image.Image]:
    try:
        return image.filter(ImageFilter.GaussianBlur(radius=radius))
    except Exception as e:
        print(f"Error during Gaussian blur attack: {e}")
        return None


def attack_median_filter(image: Image.Image, size: int) -> Optional[Image.Image]:
    try:
        return image.filter(
            ImageFilter.MedianFilter(size=size if size % 2 != 0 else size + 1)
        )  # Size must be odd
    except Exception as e:
        print(f"Error during Median filter attack: {e}")
        return None


def attack_cropping(
    image: Image.Image, crop_percent: float
) -> Optional[Image.Image]:
    try:
        w, h = image.size
        crop_w = int(w * crop_percent / 2)
        crop_h = int(h * crop_percent / 2)
        # Crop from center: (left, upper, right, lower)
        cropped_img = image.crop((crop_w, crop_h, w - crop_w, h - crop_h))
        # To test robustness, some methods might require original size.
        # For now, we extract from the cropped image.
        # If a method needs full size, it will fail.
        # Optionally, resize back to original:
        # return cropped_img.resize((w,h), Image.Resampling.LANCZOS)
        return cropped_img
    except Exception as e:
        print(f"Error during Cropping attack: {e}")
        return None


def attack_rotation(image: Image.Image, angle: float) -> Optional[Image.Image]:
    try:
        # Rotate and expand to fit, fill background with white (or black)
        return image.rotate(
            angle, expand=True, fillcolor="white", resample=Image.Resampling.BICUBIC
        )
    except Exception as e:
        print(f"Error during Rotation attack: {e}")
        return None


def attack_resizing(
    image: Image.Image, scale_factor: float
) -> Optional[Image.Image]:
    try:
        original_size = image.size
        w, h = image.size
        small_w, small_h = int(w * scale_factor), int(h * scale_factor)
        if small_w < 1 or small_h < 1:
            return None  # Avoid invalid resize

        img_small = image.resize((small_w, small_h), Image.Resampling.LANCZOS)
        return img_small.resize(original_size, Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"Error during Resizing attack: {e}")
        return None


def attack_gaussian_noise(image: Image.Image, sigma: float) -> Optional[Image.Image]:
    try:
        img_np = np.array(image.convert("RGB")).astype(float)
        noise = np.random.normal(0, sigma, img_np.shape)
        noisy_img_np = np.clip(img_np + noise, 0, 255).astype(np.uint8)
        return Image.fromarray(noisy_img_np)
    except Exception as e:
        print(f"Error during Gaussian Noise attack: {e}")
        return None


# List of attacks to perform: (attack_function, param_name, param_values_list)
ATTACKS_TO_PERFORM = [
    (attack_jpeg_compression, "quality", [95, 75, 50, 25]),
    (attack_gaussian_blur, "radius", [0.5, 1.0, 1.5]),
    (attack_median_filter, "size", [3, 5]),  # Must be odd
    (
        attack_cropping,
        "crop_percent_edges",
        [0.1, 0.25],
    ),  # 10%, 25% from each side (total 20%, 50%)
    (attack_rotation, "angle_degrees", [1, 5, -2]),
    (
        attack_resizing,
        "scale_factor_down_up",
        [0.75, 0.5],
    ),  # Scale down by factor, then back up
    (attack_gaussian_noise, "noise_sigma", [5, 10, 20]),
]


def main():
    ensure_dir(OUTPUT_DIR)

    # Clear previous output subdirectories if they exist to avoid mixed results
    # for item in os.listdir(OUTPUT_DIR):
    #     item_path = os.path.join(OUTPUT_DIR, item)
    #     if os.path.isdir(item_path):
    #         shutil.rmtree(item_path)
    # print("Cleared previous method-specific output directories.")

    steganography_methods: List[SteganographyMethod] = [
        QRCodeSteganography(),
        ReedSolomonSteganography(),
    ]

    original_image_paths = get_image_paths(INPUT_DIR)
    if not original_image_paths:
        print(f"No images found in {INPUT_DIR}. Exiting.")
        return

    print(f"Found {len(original_image_paths)} images to process.")
    print(f"Payload for embedding: {PAYLOAD_DATA.hex()} ({len(PAYLOAD_DATA)} bytes)")

    csv_header = [
        "OriginalFile",
        "StegoMethod",
        "MethodSettings",
        "PayloadOriginal_Hex",
        "EmbedTime_s",
        "WatermarkedFile",
        "PSNR_Original_vs_Watermarked",
        "SSIM_Original_vs_Watermarked",
        "AttackName",
        "AttackParam",
        "AttackedFile",
        "ExtractTime_s",
        "ExtractionSuccess",
        "ExtractedPayload_Hex",
        "PayloadMatch",
        "EmbedStatus",
        "ExtractStatus",
    ]

    with open(CSV_RESULTS_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(csv_header)

        for img_path in original_image_paths:
            original_filename = os.path.basename(img_path)
            print(f"\n--- Processing Original Image: {original_filename} ---")

            try:
                original_pil_image = Image.open(img_path)
                original_pil_image_for_metrics = (
                    original_pil_image.copy()
                )  # Keep a pristine copy for metrics
            except UnidentifiedImageError:
                print(f"Cannot identify image file {img_path}. Skipping.")
                # Write a row indicating this failure?
                writer.writerow(
                    [
                        original_filename,
                        "N/A",
                        "N/A",
                        PAYLOAD_DATA.hex(),
                        0,
                        "N/A",
                        None,
                        None,
                        "ImageLoadError",
                        "N/A",
                        "N/A",
                        0,
                        False,
                        None,
                        False,
                        "Failed to load original image",
                        "N/A",
                    ]
                )
                continue
            except Exception as e:
                print(f"Error loading image {img_path}: {e}. Skipping.")
                writer.writerow(
                    [
                        original_filename,
                        "N/A",
                        "N/A",
                        PAYLOAD_DATA.hex(),
                        0,
                        "N/A",
                        None,
                        None,
                        "ImageLoadError",
                        str(e),
                        "N/A",
                        0,
                        False,
                        None,
                        False,
                        f"Failed to load original image: {e}",
                        "N/A",
                    ]
                )
                continue

            for method in steganography_methods:
                method_name = method.get_name()
                method_settings = (
                    method.get_default_settings()
                )  # Or allow overriding
                method_output_dir = os.path.join(OUTPUT_DIR, method_name)
                ensure_dir(method_output_dir)
                attacked_img_dir = os.path.join(method_output_dir, "attacked_images")
                ensure_dir(attacked_img_dir)

                print(f"  Method: {method_name} with settings: {method_settings}")

                # --- Embedding ---
                embed_start_time = time.time()
                # Pass a copy of the original image to embed, in case it's modified internally
                # or if the method needs to resize it.
                stego_image_pil, embed_status = method.embed(
                    original_pil_image.copy(), PAYLOAD_DATA, method_settings
                )
                embed_time = time.time() - embed_start_time

                watermarked_file_path = ""
                psnr_val, ssim_val = None, None

                if stego_image_pil:
                    base_name, ext = os.path.splitext(original_filename)
                    watermarked_filename = f"{base_name}_watermarked_{method_name}{ext if ext else '.png'}"  # ensure extension
                    watermarked_file_path = os.path.join(
                        method_output_dir, watermarked_filename
                    )
                    try:
                        stego_image_pil.save(watermarked_file_path)
                        # Ensure the original image used for metrics matches the dimensions of the stego image
                        # if the embedding process resized the image.
                        # The steganography method's embed function should handle input image size expectations.
                        # For QR, it resizes. For RS, it might.
                        # We will use the original_pil_image_for_metrics which has original dimensions.
                        # The calculate_psnr/ssim functions will handle resizing one to match the other if needed.
                        psnr_val = calculate_psnr(
                            original_pil_image_for_metrics, stego_image_pil
                        )
                        ssim_val = calculate_ssim(
                            original_pil_image_for_metrics, stego_image_pil
                        )
                    except Exception as e:
                        embed_status += (
                            f" | Error saving watermarked image or calc metrics: {e}"
                        )
                        stego_image_pil = None  # Mark as failed if save fails

                # --- Extraction from non-attacked watermarked image ---
                if stego_image_pil:
                    extract_direct_start_time = time.time()
                    extracted_payload_direct, extract_direct_status = method.extract(
                        stego_image_pil, method_settings
                    )
                    extract_direct_time = time.time() - extract_direct_start_time

                    direct_match = False
                    direct_payload_hex = None
                    if extracted_payload_direct is not None:
                        direct_payload_hex = extracted_payload_direct.hex()
                        if extracted_payload_direct == PAYLOAD_DATA:
                            direct_match = True

                    writer.writerow(
                        [
                            original_filename,
                            method_name,
                            str(method_settings),
                            PAYLOAD_DATA.hex(),
                            round(embed_time, 4),
                            watermarked_file_path,
                            round(psnr_val, 2) if psnr_val is not None else None,
                            round(ssim_val, 4) if ssim_val is not None else None,
                            "NoAttack",
                            "N/A",
                            "N/A",
                            round(extract_direct_time, 4),
                            extracted_payload_direct is not None,
                            direct_payload_hex,
                            direct_match,
                            embed_status,
                            extract_direct_status,
                        ]
                    )

                    # --- Apply Attacks and Extract ---
                    for attack_func, param_name, param_values in ATTACKS_TO_PERFORM:
                        for param_val in param_values:
                            attack_name = attack_func.__name__
                            print(
                                f"    Applying Attack: {attack_name} with {param_name}={param_val}"
                            )

                            attacked_image_pil = attack_func(
                                stego_image_pil.copy(), param_val
                            )  # Apply attack on a copy
                            attacked_img_saved_path = ""

                            if attacked_image_pil:
                                base_name, ext = os.path.splitext(original_filename)
                                attacked_filename = f"{base_name}_watermarked_{method_name}_attack_{attack_name}_{param_name}{param_val}{ext if ext else '.png'}"
                                attacked_img_saved_path = os.path.join(
                                    attacked_img_dir, attacked_filename
                                )
                                try:
                                    attacked_image_pil.save(attacked_img_saved_path)
                                except Exception as e:
                                    print(f"      Error saving attacked image: {e}")
                                    # Continue to extraction attempt if image object exists

                            if attacked_image_pil:
                                extract_attack_start_time = time.time()
                                extracted_payload_attack, extract_attack_status = (
                                    method.extract(
                                        attacked_image_pil, method_settings
                                    )
                                )
                                extract_attack_time = (
                                    time.time() - extract_attack_start_time
                                )

                                attack_match = False
                                attack_payload_hex = None
                                if extracted_payload_attack is not None:
                                    attack_payload_hex = (
                                        extracted_payload_attack.hex()
                                    )
                                    if extracted_payload_attack == PAYLOAD_DATA:
                                        attack_match = True

                                writer.writerow(
                                    [
                                        original_filename,
                                        method_name,
                                        str(method_settings),
                                        PAYLOAD_DATA.hex(),
                                        None,
                                        watermarked_file_path,
                                        None,
                                        None,  # Embed info not repeated for attack rows
                                        attack_name,
                                        f"{param_name}={param_val}",
                                        attacked_img_saved_path,
                                        round(extract_attack_time, 4),
                                        extracted_payload_attack is not None,
                                        attack_payload_hex,
                                        attack_match,
                                        embed_status,  # Carry over embed status
                                        extract_attack_status,
                                    ]
                                )
                            else:  # Attack failed to produce an image
                                writer.writerow(
                                    [
                                        original_filename,
                                        method_name,
                                        str(method_settings),
                                        PAYLOAD_DATA.hex(),
                                        None,
                                        watermarked_file_path,
                                        None,
                                        None,
                                        attack_name,
                                        f"{param_name}={param_val}",
                                        "ATTACK_FAILED_TO_PRODUCE_IMAGE",
                                        0,
                                        False,
                                        None,
                                        False,
                                        embed_status,
                                        "Attack failed to produce a valid image.",
                                    ]
                                )
                else:  # Embedding failed
                    writer.writerow(
                        [
                            original_filename,
                            method_name,
                            str(method_settings),
                            PAYLOAD_DATA.hex(),
                            round(embed_time, 4),
                            "N/A",
                            None,
                            None,
                            "N/A",
                            "N/A",
                            "N/A",
                            0,
                            False,
                            None,
                            False,
                            embed_status,
                            "Embedding failed.",
                        ]
                    )

            # Clean up original image object
            if "original_pil_image" in locals() and original_pil_image:
                original_pil_image.close()
            if (
                "original_pil_image_for_metrics" in locals()
                and original_pil_image_for_metrics
            ):
                original_pil_image_for_metrics.close()

    print(f"\nBenchmark finished. Results saved to {CSV_RESULTS_FILE}")


if __name__ == "__main__":
    # Before running, ensure you have:
    # 1. An 'input/' directory with images.
    # 2. Libraries: Pillow, numpy, scipy, PyWavelets, pyqrcode, reedsolo
    #    pip install Pillow numpy scipy PyWavelets pyqrcode reedsolo scikit-image pyzbar qreader
    # (pyzbar is for QR decoding, scikit-image for PSNR/SSIM)
    main()
