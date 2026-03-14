# Project MAVIS

![MAVIS Logo](./assets/header.png)

<div align="center">

### Media Authentication, Verification and Integrity System

[Authors](#authors) | [Presentation](https://www.canva.com/design/DAGiF3nVTpM/yGptrdL7Is37iiv2_pue8g/edit?utm_content=DAGiF3nVTpM&utm_campaign=designshare&utm_medium=link2&utm_source=sharebutton) 

</div>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/Gradio-5.x-orange.svg" alt="Gradio Version">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

---

MAVIS (Media Authentication, Verification and Integrity System) is an image steganography toolkit that uses advanced **wavelet-based DCT watermarking** combined with **QR codes**, **Reed-Solomon Encoding** and **GAN-based watermarking** to embed invisible, tamper-resistant data into images. The project provides a web-based Gradio UI for embedding, extracting, and benchmarking watermarks.

> [!NOTE]  
> We are still awaiting the publish of our research paper behind this project which was presented at the MIND 2025 conference.

### Key Features

- 🔐 **Cryptographic Image Signing** - Device-level image hash signing with RSA key pairs.
- 🌊 **Wavelet-DCT Watermarking** - Resilient invisible watermarks that survive compression and social media sharing.
- 📱 **QR Code Embedding** - Encodes provenance data in QR codes embedded as watermarks.
- 📜 **Certificate Generation** - Creates tamper-proof certificates with timestamps, user info, and device data.
- ✅ **Image Verification** - Extracts and validates embedded watermarks and certificates.

---

## Architecture

![MAVIS Architecture](./assets/architecture.png)

---

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- ZBar library (for QR code reading)

### Installation

#### Using uv (Recommended)

```bash
# Clone the repository
git clone git@github.com:Project-MAVIS/MAVIS.git
cd MAVIS

# Install dependencies
make install

# Start the Gradio web UI
python3 -m mavis.demo.demo_ui
```

The UI will be available at `http://localhost:7860`

#### Using pip

```bash
# Clone the repository
git clone <repository-url>
cd MAVIS

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the project
pip install -e .

# Start the Gradio web UI
python3 -m mavis.demo.demo_ui
```

---

## Usage

MAVIS provides a Gradio-based demo UI with two main workflows: **Image Capture & Certification** and **Image Verification**.

### Tab 1: Capture & Certify

This tab emulates an iPhone's camera and Secure Enclave to demonstrate the full image certification process:

1. **Device Registration**
   - The system emulates an iPhone's Secure Enclave, generating an RSA key pair
   - The private key remains inaccessible (hardware-protected), only the public key is shared
   - A unique User ID and Device ID are assigned to the registered device

2. **Image Capture & Signing**
   - User captures/uploads an image (emulating an iPhone camera)
   - Before the image becomes accessible, it is signed using the Secure Enclave's private key
   - The signed image hash + public key are sent to the MAVIS server

3. **Server-Side Processing**
   - The server verifies the signature using the public key to confirm image integrity
   - A certificate is created containing: timestamp, image ID, user ID, device ID, username, and device name
   - The certificate is hashed and converted to a QR code

4. **Watermark Embedding**
   - The QR code (containing the certificate hash) is invisibly embedded into the image using DWT-DCT steganography
   - The encrypted certificate is stored in the image's EXIF metadata
   - Both the original image and certificate are stored in the server database

5. **Output**
   - The certified image is returned to the user
   - This image can be shared anywhere while retaining its provenance data

### Tab 2: Verify Image

This tab allows users to verify the authenticity of any image:

1. **Upload Image**
   - User uploads an image to the verification tab

2. **Primary Verification (EXIF + QR)**
   - Server extracts the encrypted certificate from the EXIF metadata
   - Server decrypts and parses the certificate
   - Server extracts the certificate hash from the embedded QR watermark
   - If the extracted hash matches the certificate hash → **Image Verified ✓**

3. **WhatsApp Scenario (Metadata Stripped)**
   - If EXIF metadata is missing (e.g., image was shared via WhatsApp)
   - The QR code hash is extracted from the pixels
   - This hash is used to look up the original certificate and image from the database
   - The server returns:
     - The uploaded image
     - The original certified image
     - The certificate information
   - User can compare and verify authenticity

---

### Project Structure

This repository contains only the final codebase of the project[^1].

```
MAVIS/
├── mavis/                      # Main package
│   ├── algorithms/             # Steganography algorithms
│   │   ├── core/               # Core utilities
│   │   │   ├── qr_code.py      # QR code generation & DWT-DCT embedding
│   │   │   └── reed_solomon.py # Reed-Solomon error correction
│   │   ├── qr_steganography.py # QR-based steganography method
│   │   ├── rs_steganography.py # Reed-Solomon steganography method
│   │   └── steganography_interface.py  # Abstract base class
│   ├── benchmark/              # Benchmarking utilities
│   │   └── benchmark.py
│   ├── cmd/                    # Command-line interface
│   │   └── ui.py               # UI launcher entry point
│   └── ui/                     # Gradio web interface
│       └── ui.py               # Main Gradio app
├── scripts/                    # Setup scripts
│   ├── keys.sh                 # RSA key pair generation
│   └── setup.sh                # Legacy setup script
├── scratch/                    # Experimental/demo code
├── pyproject.toml              # Project configuration & dependencies
├── Makefile                    # Development commands
└── uv.lock                     # Dependency lock file
```

## Technical Details

### Watermarking Algorithm

MAVIS uses a **Wavelet-DCT (Discrete Cosine Transform)** hybrid approach:

1. **Wavelet Decomposition** - Image is decomposed using PyWavelets (DWT)
2. **QR Code Generation** - Payload data is encoded into a QR code
3. **DCT Transform** - Applied to wavelet subband coefficients
4. **Embedding** - QR code is embedded in mid-frequency coefficients (robust to compression)
5. **Reconstruction** - Image is reconstructed with minimal visual artifacts

### Default Parameters

| Parameter     | Default Value | Description                     |
| ------------- | ------------- | ------------------------------- |
| `alpha`       | `25.0`        | Embedding strength              |
| `wavelet`     | `db4`         | Wavelet type (Daubechies-4)     |
| `subband`     | `HL`          | Wavelet subband for embedding   |
| `repetitions` | `1`           | Number of embedding repetitions |

### Resilience Features

- ✅ JPEG compression (up to 70% quality)
- ✅ Social media compression (WhatsApp, Instagram)
- ✅ Minor cropping and resizing
- ✅ Color adjustments

### Certificate Structure

```
┌──────────────────────────────────────────────┐
│ cert_len │ timestamp │ image_id │ user_id   │
│ device_id │ username │ device_name           │
└──────────────────────────────────────────────┘
```

### Quality Metrics

The benchmark tab calculates:

- **PSNR** (Peak Signal-to-Noise Ratio) - Image quality metric
- **SSIM** (Structural Similarity Index) - Perceptual quality metric
- **BER** (Bit Error Rate) - Payload accuracy
- **Exact Match** - Whether extracted payload matches original

---

## Authors

- **Omkar Wagholikar** - [omkarrwagholikar@gmail.com](mailto:omkarrwagholikar@gmail.com)
- **Shantanu Wable** - [shantanuwable2003@gmail.com](mailto:shantanuwable2003@gmail.com)
- **Soaham Pimparkar** - [soahampimparkar@gmail.com](mailto:soahampimparkar@gmail.com)
- **Chinmay Patil** - [crpatil1901@gmail.com](mailto:crpatil1901@gmail.com)

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [PyWavelets](https://pywavelets.readthedocs.io/) - Wavelet transforms
- [Gradio](https://gradio.app/) - Web UI framework
- [QReader](https://github.com/Eric-Canas/qreader) - QR code reading
- [Pillow](https://python-pillow.org/) - Image processing
- [scikit-image](https://scikit-image.org/) - Image quality metrics.

## Footnotes

### ZBar Library Setup

ZBar is required for opencv2 to detect Reed-Solomon code during extraction.

**macOS:**

```bash
brew install zbar
export DYLD_LIBRARY_PATH=$(brew --prefix zbar)/lib:$DYLD_LIBRARY_PATH
```

**Ubuntu/Debian:**

```bash
sudo apt-get install libzbar0
```

**Windows:**

ZBar is included via the `pyzbar` package - no additional installation needed.

[^1]: The majority of the code in this repository was written during development, in [another repository](https://github.com/Project-MAVIS/Backend), but was later ported to this repository for better organization and to keep the codebase clean.
