# Copyright (c) 2026 Project MAVIS Authors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, subject to the conditions in the LICENSE file.
#
# See the LICENSE file for more details.

from PIL import Image
from typing import Tuple, Optional, Dict, Any

from mavis.algorithms.steganography_interface import SteganographyMethod
import mavis.algorithms.core.reed_solomon as reed_solomon_core


class ReedSolomonSteganography(SteganographyMethod):
    def get_name(self) -> str:
        return "ReedSolomon_DCT"

    def get_default_settings(self) -> Dict[str, Any]:
        return {
            "strength": 10,  # Embedding strength
            "max_dimension": 1024,  # For initial resize
            "length_ecc_symbols": 4,  # ECC symbols for payload length (e.g. 4 bytes for length, 4 ECC symbols)
            "payload_ecc_factor": 0.5,  # Payload ECC symbols = payload_length * factor (e.g. 0.5 -> 50% ECC)
        }

    def embed(
        self,
        image: Image.Image,
        payload: bytes,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Image.Image], Any]:
        config = self.get_default_settings()
        if settings:
            config.update(settings)

        strength = config["strength"]
        max_dim = config["max_dimension"]
        len_ecc_nsym = config["length_ecc_symbols"]
        payload_ecc_factor = config["payload_ecc_factor"]

        img_cv = reed_solomon_core.pil_to_cv2(image)

        embedded_img_cv, status_msgs = reed_solomon_core.embed_reed_solomon_dct(
            img_cv=img_cv,
            payload=payload,
            strength=strength,
            max_dimension=max_dim,
            len_ecc_nsym=len_ecc_nsym,
            payload_ecc_factor=payload_ecc_factor,
        )

        if embedded_img_cv is None:
            return image, "\n".join(status_msgs)

        return reed_solomon_core.cv2_to_pil(embedded_img_cv), "\n".join(status_msgs)

    def extract(
        self, image: Image.Image, settings: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[bytes], Any]:
        config = self.get_default_settings()
        if settings:
            config.update(settings)

        strength = config["strength"]
        len_ecc_nsym = config["length_ecc_symbols"]
        payload_ecc_factor = config["payload_ecc_factor"]

        img_cv = reed_solomon_core.pil_to_cv2(image)

        extracted_payload, status_msgs = reed_solomon_core.extract_reed_solomon_dct(
            img_cv=img_cv,
            strength=strength,
            len_ecc_nsym=len_ecc_nsym,
            payload_ecc_factor=payload_ecc_factor,
        )

        return extracted_payload, "\n".join(status_msgs)
