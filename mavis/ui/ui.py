# Copyright (c) 2026 Project MAVIS Authors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, subject to the conditions in the LICENSE file.
#
# See the LICENSE file for more details.

import gradio as gr
from PIL import Image
import numpy as np
import tempfile
import os
import json
from typing import Dict

from mavis.algorithms.steganography_interface import SteganographyMethod
from mavis.algorithms.qr_steganography import QRCodeSteganography

# --- Registry of available steganography methods ---
METHODS: Dict[str, SteganographyMethod] = {}


def register_methods():
    """Register all available steganography methods."""
    methods = [
        # ReedSolomonSteganography(),
        QRCodeSteganography(),
    ]
    for method in methods:
        METHODS[method.get_name()] = method


# Initialize methods on module load
register_methods()


# --- Helper to save PIL image temporarily ---
def save_temp_pil(image_pil, suffix=".png"):
    """Saves PIL image to a temp file, returns path."""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
            fmt = "PNG" if suffix.lower() == ".png" else "JPEG"
            image_pil.save(temp_file.name, format=fmt)
            return temp_file.name
    except Exception as e:
        print(f"Error saving temp file: {e}")
        return None


# --- Gradio Backend Functions ---


def gradio_embed(
    original_image_pil: Image.Image, payload_str: str, method_name: str
):
    """Handles the embedding process for Gradio."""
    if original_image_pil is None or not payload_str or not method_name:
        return (
            None,
            None,
            "Missing input: Please provide image, payload, and method.",
        )

    if method_name not in METHODS:
        return None, None, f"Error: Unknown method '{method_name}'."

    method = METHODS[method_name]

    # Convert string payload to bytes
    payload_bytes = payload_str.encode("utf-8")

    # Call the embedding function
    stego_image_pil, status = method.embed(original_image_pil, payload_bytes)

    if stego_image_pil:
        # Save result to temp file for download link
        temp_file_path = save_temp_pil(
            stego_image_pil, suffix=".png"
        )  # Save lossless PNG
        if temp_file_path:
            return stego_image_pil, temp_file_path, f"Embedding Status:\n{status}"
        else:
            return (
                stego_image_pil,
                None,
                f"Embedding Status:\n{status}\n\nError: Failed to create download file.",
            )
    else:
        return None, None, f"Embedding Failed:\n{status}"


def compress_image(image_pil: Image.Image, quality: int = 75) -> Image.Image:
    """Compress an image using JPEG compression and return as PIL Image."""
    import io

    # Convert to RGB if necessary (JPEG doesn't support alpha channel)
    if image_pil.mode in ("RGBA", "P"):
        image_pil = image_pil.convert("RGB")

    # Compress using JPEG
    buffer = io.BytesIO()
    image_pil.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)

    # Load back as PIL Image
    compressed_image = Image.open(buffer).copy()
    buffer.close()

    return compressed_image


def gradio_compress_and_extract(
    watermarked_image_pil, quality: int, method_name: str, original_payload_str: str
):
    """Compress the watermarked image and attempt to extract the payload."""
    if watermarked_image_pil is None or not method_name:
        return (
            None,
            None,
            None,
            "Missing input: Please provide watermarked image and method.",
        )

    if method_name not in METHODS:
        return None, None, None, f"Error: Unknown method '{method_name}'."

    method = METHODS[method_name]

    # Compress the image
    compressed_image = compress_image(watermarked_image_pil, quality=int(quality))

    # Extract payload from compressed image
    extracted_payload, extract_status = method.extract(compressed_image)

    # Convert bytes to string for display
    extracted_payload_str = None
    if extracted_payload is not None:
        try:
            extracted_payload_str = extracted_payload.decode("utf-8")
        except UnicodeDecodeError:
            extracted_payload_str = extracted_payload.hex()

    # Calculate metrics if original payload was provided
    metrics_str = None
    if original_payload_str:
        orig_np = np.array(watermarked_image_pil.convert("RGB"))
        comp_np = np.array(compressed_image.convert("RGB"))

        metrics = calculate_metrics(
            orig_np, comp_np, original_payload_str, extracted_payload
        )
        metrics["compression_quality"] = int(quality)
        metrics_str = json.dumps(metrics, indent=2)

    status = (
        f"Compression Quality: {quality}%\n\nExtraction Status:\n{extract_status}"
    )

    return compressed_image, extracted_payload_str, metrics_str, status


def calculate_metrics(
    orig_np: np.ndarray,
    water_np: np.ndarray,
    original_payload: str,
    extracted_payload: bytes | None,
) -> dict:
    """Calculate image quality and payload accuracy metrics."""
    from skimage.metrics import peak_signal_noise_ratio, structural_similarity

    metrics = {}

    try:
        # Image quality metrics
        metrics["psnr"] = float(peak_signal_noise_ratio(orig_np, water_np))
        ssim_result = structural_similarity(
            orig_np,
            water_np,
            channel_axis=2 if len(orig_np.shape) == 3 else None,
        )
        # structural_similarity returns float by default (tuple only when full=True)
        metrics["ssim"] = float(ssim_result)  # type: ignore[arg-type]
    except Exception as e:
        metrics["error"] = f"Error calculating image metrics: {e}"
        return metrics

    # Payload accuracy
    try:
        original_bytes = original_payload.encode("utf-8")
        if extracted_payload is not None:
            # Bit error rate
            min_len = min(len(original_bytes), len(extracted_payload))
            if min_len > 0:
                bit_errors = sum(
                    bin(a ^ b).count("1")
                    for a, b in zip(
                        original_bytes[:min_len], extracted_payload[:min_len]
                    )
                )
                total_bits = min_len * 8
                metrics["ber"] = bit_errors / total_bits if total_bits > 0 else 0.0

            # Exact match
            metrics["exact_match"] = original_bytes == extracted_payload
            metrics["payload_accuracy"] = (
                1.0 if original_bytes == extracted_payload else 0.0
            )
        else:
            metrics["ber"] = 1.0
            metrics["exact_match"] = False
            metrics["payload_accuracy"] = 0.0
    except Exception as e:
        metrics["payload_error"] = f"Error comparing payloads: {e}"

    return metrics


def gradio_benchmark(
    original_image_pil, watermarked_image_pil, original_payload_str, method_name
):
    """Handles the extraction and benchmarking process for Gradio."""
    if (
        original_image_pil is None
        or watermarked_image_pil is None
        or not original_payload_str
        or not method_name
    ):
        return (
            None,
            None,
            "Missing input: Please provide both images, original payload, and method.",
        )

    if method_name not in METHODS:
        return None, None, f"Error: Unknown method '{method_name}'."

    method = METHODS[method_name]

    # --- Extraction ---
    extracted_payload, extract_status = method.extract(watermarked_image_pil)

    # Convert extracted bytes to string for display
    extracted_payload_str = None
    if extracted_payload is not None:
        try:
            extracted_payload_str = extracted_payload.decode("utf-8")
        except UnicodeDecodeError:
            extracted_payload_str = extracted_payload.hex()

    # --- Benchmarking ---
    # Load images as NumPy arrays for metric calculation
    try:
        orig_np = np.array(original_image_pil.convert("RGB"))
        water_np = np.array(watermarked_image_pil.convert("RGB"))

        # Ensure dimensions match for metrics (optional but safer)
        if orig_np.shape != water_np.shape:
            print(
                f"Warning: Image shapes differ ({orig_np.shape} vs {water_np.shape}). Resizing watermarked for metrics."
            )
            h, w = orig_np.shape[:2]
            # Use PIL for consistent resizing
            water_pil_resized = Image.fromarray(water_np).resize(
                (w, h), Image.Resampling.LANCZOS
            )
            water_np = np.array(water_pil_resized)

    except Exception as e:
        return (
            extracted_payload_str,
            None,
            f"Extraction Status:\n{extract_status}\n\nError loading images for benchmarking: {e}",
        )

    # Calculate metrics
    metrics = calculate_metrics(
        orig_np, water_np, original_payload_str, extracted_payload
    )

    # Format metrics for display
    metrics_str = json.dumps(metrics, indent=2)  # Pretty print JSON
    status = f"Extraction Status:\n{extract_status}\n\nBenchmarking Status:\n{metrics.get('error', 'Completed')}"

    return extracted_payload_str, metrics_str, status


def gradio_extract(watermarked_image_pil, method_name):
    """Handles the extraction process for Gradio (without benchmarking)."""
    if watermarked_image_pil is None or not method_name:
        return None, "Missing input: Please provide watermarked image and method."

    if method_name not in METHODS:
        return None, f"Error: Unknown method '{method_name}'."

    method = METHODS[method_name]

    # --- Extraction ---
    extracted_payload, extract_status = method.extract(watermarked_image_pil)

    # Convert bytes to string for display
    extracted_payload_str = None
    if extracted_payload is not None:
        try:
            extracted_payload_str = extracted_payload.decode("utf-8")
        except UnicodeDecodeError:
            extracted_payload_str = extracted_payload.hex()

    return extracted_payload_str, f"Extraction Status:\n{extract_status}"


# --- Build Gradio UI ---

with gr.Blocks(theme="soft") as demo:
    gr.Markdown("# Project MAVIS: Embedding, Extraction & Benchmarking")

    method_choices = list(METHODS.keys())

    with gr.Tabs():
        # --- Embed Tab ---
        with gr.TabItem("Embed Watermark"):
            gr.Markdown(
                "Upload an image, enter a payload, select a method, and embed."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    embed_input_image = gr.Image(
                        type="pil",
                        label="1. Original Image",
                        sources=["upload", "webcam"],
                    )
                    embed_payload_text = gr.Textbox(
                        label="2. Payload (Text to Embed)", lines=3
                    )
                    embed_method_dd = gr.Dropdown(
                        choices=method_choices,
                        label="3. Embedding Method",
                        value=method_choices[0] if method_choices else None,
                    )
                    embed_button = gr.Button("Embed Watermark", variant="primary")
                with gr.Column(scale=1):
                    embed_output_image = gr.Image(
                        type="pil", label="Watermarked Image (Result)"
                    )
                    embed_download_file = gr.File(
                        label="Download Watermarked Image (PNG)"
                    )
                    embed_status_text = gr.Textbox(
                        label="Status", lines=5, interactive=False
                    )

        # --- Extract Payload Tab ---
        with gr.TabItem("Extract Payload"):
            gr.Markdown(
                "Upload a watermarked image and select the method used for embedding to extract the hidden payload."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    extract_water_image = gr.Image(
                        type="pil",
                        label="1. Watermarked Image",
                        sources=["upload", "webcam"],
                    )
                    extract_method_dd = gr.Dropdown(
                        choices=method_choices,
                        label="2. Method Used for Embedding",
                        value=method_choices[0] if method_choices else None,
                    )
                    extract_button = gr.Button("Extract Payload", variant="primary")
                with gr.Column(scale=1):
                    extract_payload_output = gr.Textbox(
                        label="Extracted Payload", lines=10, interactive=False
                    )
                    extract_status_text = gr.Textbox(
                        label="Status", lines=5, interactive=False
                    )

        # --- Benchmark Tab ---
        with gr.TabItem("Benchmark"):
            gr.Markdown(
                "Upload the original and watermarked images, provide the original payload, select the method used for embedding, and calculate metrics."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    bench_orig_image = gr.Image(
                        type="pil",
                        label="1. Original Image",
                        sources=["upload", "webcam"],
                    )
                    bench_water_image = gr.Image(
                        type="pil",
                        label="2. Watermarked Image",
                        sources=["upload", "webcam"],
                    )
                    bench_orig_payload = gr.Textbox(
                        label="3. Original Payload (Exact text embedded)", lines=3
                    )
                    bench_method_dd = gr.Dropdown(
                        choices=method_choices,
                        label="4. Method Used for Embedding",
                        value=method_choices[0] if method_choices else None,
                    )
                    bench_button = gr.Button(
                        "Extract & Calculate Metrics", variant="primary"
                    )
                with gr.Column(scale=1):
                    bench_extracted_payload = gr.Textbox(
                        label="Extracted Payload", lines=3, interactive=False
                    )
                    bench_metrics_display = gr.JSON(
                        label="Calculated Metrics"
                    )  # Use JSON component
                    # bench_metrics_display = gr.Label(label="Calculated Metrics") # Alternative: Label
                    bench_status_text = gr.Textbox(
                        label="Status", lines=5, interactive=False
                    )

        # --- Compression Tolerance Tab ---
        with gr.TabItem("Compression Tolerance"):
            gr.Markdown(
                "Test the robustness of the embedded watermark against JPEG compression. "
                "Upload a watermarked image, select compression quality, and check if the payload can still be extracted."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    compress_water_image = gr.Image(
                        type="pil",
                        label="1. Watermarked Image",
                        sources=["upload", "webcam"],
                    )
                    compress_quality_slider = gr.Slider(
                        minimum=1,
                        maximum=100,
                        value=75,
                        step=1,
                        label="2. JPEG Compression Quality (%)",
                        info="Lower values = more compression = more degradation",
                    )
                    compress_method_dd = gr.Dropdown(
                        choices=method_choices,
                        label="3. Method Used for Embedding",
                        value=method_choices[0] if method_choices else None,
                    )
                    compress_orig_payload = gr.Textbox(
                        label="4. Original Payload (optional, for metrics)",
                        lines=2,
                        placeholder="Enter the original payload to calculate accuracy metrics",
                    )
                    compress_button = gr.Button(
                        "Compress & Extract", variant="primary"
                    )
                with gr.Column(scale=1):
                    compress_output_image = gr.Image(
                        type="pil", label="Compressed Image"
                    )
                    compress_extracted_payload = gr.Textbox(
                        label="Extracted Payload", lines=5, interactive=False
                    )
                    compress_metrics_display = gr.JSON(label="Metrics")
                    compress_status_text = gr.Textbox(
                        label="Status", lines=5, interactive=False
                    )

    # --- Connect Components ---
    embed_button.click(
        fn=gradio_embed,
        inputs=[embed_input_image, embed_payload_text, embed_method_dd],
        outputs=[embed_output_image, embed_download_file, embed_status_text],
    )

    extract_button.click(
        fn=gradio_extract,
        inputs=[extract_water_image, extract_method_dd],
        outputs=[extract_payload_output, extract_status_text],
    )

    bench_button.click(
        fn=gradio_benchmark,
        inputs=[
            bench_orig_image,
            bench_water_image,
            bench_orig_payload,
            bench_method_dd,
        ],
        outputs=[bench_extracted_payload, bench_metrics_display, bench_status_text],
    )

    compress_button.click(
        fn=gradio_compress_and_extract,
        inputs=[
            compress_water_image,
            compress_quality_slider,
            compress_method_dd,
            compress_orig_payload,
        ],
        outputs=[
            compress_output_image,
            compress_extracted_payload,
            compress_metrics_display,
            compress_status_text,
        ],
    )

# --- Launch the Gradio App ---
if __name__ == "__main__":
    # Clean up old temp files (optional)
    temp_dir = tempfile.gettempdir()
    for filename in os.listdir(temp_dir):
        if filename.endswith((".png", ".jpg", ".jpeg")):
            try:
                # Add more specific prefix checks if needed
                # os.remove(os.path.join(temp_dir, filename))
                pass  # Be cautious with auto-deletion
            except OSError:
                pass
    # Launch
    demo.launch()
