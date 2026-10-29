from io import BytesIO

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
import logging

logger = logging.getLogger(__name__)


class CloudinaryService:
    MAX_IMAGE_SIZE = 5 * 1024 * 1024

    ALLOWED_CONTENT_TYPES = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    async def upload_product_image(self, file: UploadFile) -> dict:
        if file.content_type not in self.ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Only JPG, PNG, and WebP images are allowed.",
            )

        contents = await file.read()

        if not contents:
            raise HTTPException(
                status_code=400,
                detail="Please select an image to upload.",
            )

        if len(contents) > self.MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=400,
                detail="Image size must not exceed 5 MB.",
            )

        try:
            image = Image.open(BytesIO(contents))
            image.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is not a valid image.",
            )

        try:
            result = cloudinary.uploader.upload(
                BytesIO(contents),
                folder="ministore/products",
                resource_type="image",
                allowed_formats=["jpg", "jpeg", "png", "webp"],
            )

            return {
                "image_url": result["secure_url"],
                "public_id": result["public_id"],
            }

        except Exception:
            logger.exception("Cloudinary product image upload failed")
            raise HTTPException(
                status_code=502,
                detail="Failed to upload the image. Please try again.",
            )

    def delete_product_image(self, public_id: str) -> dict:
        try:
            return cloudinary.uploader.destroy(
                public_id,
                resource_type="image",
            )
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="Failed to delete the image from Cloudinary.",
            )
