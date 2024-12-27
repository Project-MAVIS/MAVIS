import cv2
from snh import *


# Function to embed a hash as an invisible watermark in an image
def embed_watermark(image, hash_value):
    # Load image
    height, width, _ = image.shape

    # Convert the hash to binary (256 bits for SHA-256)
    binary_hash = "".join(
        format(int(h, 16), "04b") for h in hash_value
    )  # Convert hex to binary

    # Embed the binary hash into the image
    binary_index = 0
    for i in range(height):
        for j in range(width):
            if binary_index >= len(binary_hash):
                break
            # Get the RGB values
            r, g, b = image[i, j]
            # Modify the LSB of the blue channel with binary hash bit
            b = (b & 254) | int(binary_hash[binary_index])  # Set LSB to the hash bit
            b = max(0, min(255, b))
            image[i, j] = [r, g, b]
            binary_index += 1
        if binary_index >= len(binary_hash):
            break
    
    # Return the watermarked image
    return image


# Function to extract the watermark from an image
def extract_watermark(watermarked_image_path):
    # Load the watermarked image
    image = cv2.imread(watermarked_image_path)
    height, width, _ = image.shape

    # Extract binary hash from the image
    extracted_binary_hash = ""
    for i in range(height):
        for j in range(width):
            if len(extracted_binary_hash) >= 256:
                break
            # Get the LSB of the blue channel
            b = image[i, j][2]
            extracted_binary_hash += str(b & 1)  # Append the LSB
        if len(extracted_binary_hash) >= 256:
            break

    # Convert the binary hash back to hexadecimal
    extracted_hash = "".join(
        format(int(extracted_binary_hash[i : i + 4], 2), "x") for i in range(0, 256, 4)
    )
    return extracted_hash