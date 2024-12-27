import streamlit as st
import numpy as np
from PIL import Image

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from dct import WaveletDCTWatermark
watermarker = WaveletDCTWatermark()

# Load the private key from the file
with open(".keys/private.key", "rb") as private_file:
    private_key = serialization.load_pem_private_key(
        private_file.read(), password=None, backend=default_backend()
    )

# Load the public key from the file
with open(".keys/public.key", "rb") as public_file:
    public_key = serialization.load_pem_public_key(
        public_file.read(), backend=default_backend()
    )

st.title("Signing and Hashing")

st.markdown("## Upload Image and Hash")
uploaded_image = st.file_uploader("Image file", type=["jpg", "jpeg", "png"])
uploaded_hash = st.file_uploader("Hash file (QR Code)", type=["png", "jpg", "jpeg"])

st.markdown("## Uploaded Image")
if uploaded_image is not None and uploaded_hash is not None:
    st.image(uploaded_image, caption="Uploaded Image", use_container_width=True)
    st.image(uploaded_hash, caption="Uploaded Hash", use_container_width=True)
    
    # Embed the hash into the image
    watermarked_image_array = watermarker.fwatermark_image(uploaded_image, uploaded_hash)
    watermarked_image = Image.fromarray(watermarked_image_array)
    
    st.markdown("## Watermarked Image")
    st.image(watermarked_image, caption="Watermarked Image", use_container_width=True)
    
    st.markdown("## Extracting the Hash from the Watermarked Image")
    
    # Extract the hash from the watermarked image
    extracted_watermark_array = watermarker.frecover_watermark(watermarked_image)
    extracted_watermark = Image.fromarray(extracted_watermark_array)
    
    st.markdown("### Extracted Hash")
    st.image(extracted_watermark, caption="Extracted Hash", use_container_width=True)