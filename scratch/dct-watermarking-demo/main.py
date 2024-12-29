import streamlit as st
import numpy as np
from PIL import Image
from PIL.ExifTags import TAGS
from hashlib import sha256
import pprint
import io
import pyqrcode
# import cv2

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from dct import WaveletDCTWatermark
watermarker = WaveletDCTWatermark()
# decoder = cv2.QRCodeDetector()

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
    
original_hash = None
extracted_hash = None

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
        
        original_hash = sha256(ui.tobytes()).hexdigest()
        half_hash = original_hash[:32]
        st.markdown(f"""### Image Hash (SHA256)\n\n```\n{original_hash}\n```""")
        
        qr = pyqrcode.create(original_hash)
        buffer = io.BytesIO()
        qr.png(buffer, scale=5)
        
        st.subheader("QR Code of the Image Hash")
        st.image(buffer)
        
        # st.image(uploaded_hash, caption="Uploaded Hash", use_container_width=True)
        
        # Embed the full hash into the image
        watermarked_image_array = watermarker.fwatermark_image(uploaded_image, buffer)
        watermarked_image = Image.fromarray(watermarked_image_array)
        
        st.markdown(f"""## Watermarked Image""")
        
        st.markdown("### Full Hash Embedded Image\nThe full hash of the image is embedded into the image using DCT watermarking.")
        st.image(watermarked_image, caption="Full Hash Watermarked Image")

        save_watermarked_image = st.button("Save Watermarked Image")
        if save_watermarked_image:
            watermarked_image.save("watermarked_image.png")
            st.write("Watermarked image saved as watermarked_image.png")
            
        hqr = pyqrcode.create(half_hash)
        hbuffer = io.BytesIO()
        hqr.png(hbuffer, scale=5)
            
        # Embed the half hash into the image
        hwatermarked_image_array = watermarker.fwatermark_image(uploaded_image, hbuffer)
        hwatermarked_image = Image.fromarray(hwatermarked_image_array)
        
        st.markdown("### Half Hash Embedded Image\nThe half hash of the image is embedded into the image using DCT watermarking.")
        st.image(hwatermarked_image, caption="Half Hash Watermarked Image")
        
        hsave_watermarked_image = st.button("Save Partial Watermarked Image")
        if hsave_watermarked_image:
            hwatermarked_image.save("half_watermarked_image.png")
            st.write("Watermarked image saved as half_watermarked_image.png")
            
elif view == "Hash Extraction":
    st.markdown("## Extract Hash from Image")
    uploaded_watermarked_image = st.file_uploader("Watermarked Image file", type=["jpg", "jpeg", "png", "heic"])
    if uploaded_watermarked_image is not None:
        st.markdown("### Uploaded Watermarked Image")
        st.image(uploaded_watermarked_image, caption="Uploaded Watermarked Image")
        
        # Extract the hash from the watermarked image
        extracted_watermark_array = watermarker.frecover_watermark(Image.open(uploaded_watermarked_image))
        extracted_watermark = Image.fromarray(extracted_watermark_array)
        
        extracted_watermark.save("extracted_watermark.png")
        
        st.markdown("### Extracted Hash")
        st.image(extracted_watermark, caption="Extracted Hash")
        
        # # Decode the hash from the QR code
        # data, _, _ = decoder.detectAndDecode(cv2.imread("extracted_watermark.png"))
        # extracted_hash = data
        
        # st.markdown(f"""### Extracted Hash (SHA256)\n\n```\n{extracted_hash}\n```""")