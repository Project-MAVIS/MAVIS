# Copyright (c) 2026 Project MAVIS Authors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, subject to the conditions in the LICENSE file.
#
# See the LICENSE file for more details.

from abc import ABC, abstractmethod
from PIL import Image
from typing import Tuple, Any, Dict, Optional


class SteganographyMethod(ABC):
    """
    Abstract base class for steganography methods.
    """

    @abstractmethod
    def get_name(self) -> str:
        """Returns the name of the steganography method."""
        pass

    @abstractmethod
    def embed(
        self,
        image: Image.Image,
        payload: bytes,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Image.Image], Any]:
        """
        Embeds the payload into the image.

        Args:
            image (Image.Image): The cover image (PIL Image).
            payload (bytes): The data to embed.
            settings (Optional[Dict[str, Any]]): Method-specific settings.

        Returns:
            Tuple[Optional[Image.Image], Any]: A tuple containing:
                - The stego image (PIL Image) or None on failure.
                - Status message or metadata from the embedding process.
        """
        pass

    @abstractmethod
    def extract(
        self, image: Image.Image, settings: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[bytes], Any]:
        """
        Extracts the payload from the stego image.

        Args:
            image (Image.Image): The stego image (PIL Image).
            settings (Optional[Dict[str, Any]]): Method-specific settings.

        Returns:
            Tuple[Optional[bytes], Any]: A tuple containing:
                - The extracted payload (bytes) or None on failure/data not found.
                - Status message or metadata from the extraction process.
        """
        pass

    def get_default_settings(self) -> Dict[str, Any]:
        """
        Returns default settings for the method, if any.
        These can be overridden during embed/extract calls.
        """
        return {}
