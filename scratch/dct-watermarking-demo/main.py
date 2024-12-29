import streamlit as st
import numpy as np
from PIL import Image
from PIL.ExifTags import TAGS
from hashlib import sha256
import pprint
import io
import pyqrcode

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

st.sidebar.title("Navigation")
view = st.sidebar.radio("Go to", ["Image Watermarking", "Hash Extraction"])

if view == "Image Watermarking":
    
    st.title("Image Watermarking")

    st.markdown("## Upload Image")
    uploaded_image = st.file_uploader("Image file", type=["jpg", "jpeg", "png", "heic"])

    if uploaded_image is not None :
        st.markdown("### Uploaded Image")
        st.image(uploaded_image, caption="Uploaded Image")
        ui = Image.open(uploaded_image)
        exifdata = ui.getexif()
        ed = {}
        for tagid in exifdata:
            tagname = TAGS.get(tagid, tagid)
            value = exifdata.get(tagid)
            ed[tagname] = value
        st.markdown(f"""### Image Metadata\n\n```json\n{pprint.pformat(ed)}\n```""")
        
        image_hash = sha256(ui.tobytes()).hexdigest()
        half_hash = image_hash[:32]
        st.markdown(f"""### Image Hash\n\n```\n{image_hash}\n```""")
        
        qr = pyqrcode.create(image_hash)
        buffer = io.BytesIO()
        qr.png(buffer, scale=5)
        
        st.subheader("QR Code of the Image Hash")
        st.image(buffer)
        
        # st.image(uploaded_hash, caption="Uploaded Hash", use_container_width=True)
        
        # Embed the hash into the image
        watermarked_image_array = watermarker.fwatermark_image(uploaded_image, buffer)
        watermarked_image = Image.fromarray(watermarked_image_array)
        
        st.markdown("## Watermarked Image")
        st.image(watermarked_image, caption="Watermarked Image")
        
elif view == "Hash Extraction":
    st.markdown("## Extract Hash from Image")
    uploaded_watermarked_image = st.file_uploader("Watermarked Image file", type=["jpg", "jpeg", "png", "heic"])
    if uploaded_watermarked_image is not None:
        st.markdown("### Uploaded Watermarked Image")
        st.image(uploaded_watermarked_image, caption="Uploaded Watermarked Image")
        
        # Extract the hash from the watermarked image
        extracted_watermark_array = watermarker.frecover_watermark(Image.open(uploaded_watermarked_image))
        extracted_watermark = Image.fromarray(extracted_watermark_array)
        
        st.markdown("### Extracted Hash")
        st.image(extracted_watermark, caption="Extracted Hash")
        
        extracted_watermark.save("extracted_hash.png")
        
        qr = pyqrcode.create(extracted_watermark)
        buffer = io.BytesIO()
        qr.png(buffer, scale=5)
        
        st.subheader("QR Code of the Extracted Hash")
        st.image(buffer)