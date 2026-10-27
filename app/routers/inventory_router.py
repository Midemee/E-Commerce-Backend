from uuid import UUID
from app.services.cloudinary_service import CloudinaryService
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session
from starlette import status

from app.config.dependencies import get_session
from app.exception.product_not_found_exception import ProductNotFoundException
from app.exception.product_stock_exception import ProductStockException
from app.models.product import Product, AddProduct, UpdateProduct
from app.repositories.product_repository import ProductRepository
from app.security.dependencies import get_current_user, require_storekeeper
from app.services.inventory_service import InventoryService

cloudinary_service = CloudinaryService()
router = APIRouter(prefix="/inventory", tags=["inventory_service"])

def get_inventory_service(session: Session = Depends(get_session)) -> InventoryService:
    product_repository = ProductRepository(session)
    return InventoryService(repository=product_repository)

storekeeper_only = [Depends(require_storekeeper)]
any_logged_in_user = [Depends(get_current_user)]

@router.post("/upload-image")
async def upload_product_image(
    file: UploadFile = File(...),
    current_user=Depends(require_storekeeper),
):
    return await cloudinary_service.upload_product_image(file)

@router.post(
    "/create_product",
    response_model=Product,
    status_code=status.HTTP_201_CREATED,
    dependencies=storekeeper_only,
)
def create_new_product(
    payload: AddProduct,
    inventory_service: InventoryService = Depends(get_inventory_service),
):
    try:
        return inventory_service.add_product(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create product: {str(e)}"
        )


@router.post(
    "/update_product",
    response_model=Product,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=storekeeper_only,
)
def update_product(
    payload: UpdateProduct,
    inventory_service: InventoryService = Depends(get_inventory_service),
):
    try:
        return inventory_service.restock(payload)
    except ProductNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ProductStockException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restock/update product: {str(e)}"
        )

@router.get(
    "/get_all_products",
    response_model=list[Product],
    status_code=status.HTTP_200_OK,
    dependencies=any_logged_in_user,
)
def get_all_products(
    inventory_service: InventoryService = Depends(get_inventory_service),
):
    try:
        return inventory_service.get_all_products()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get all products: {str(e)}"
        )

@router.get(
    "/get_product",
    response_model=Product,
    status_code=status.HTTP_200_OK,
    dependencies=any_logged_in_user,
)
def get_product(
    id: UUID,
    inventory_service: InventoryService = Depends(get_inventory_service),
):
    try:
        return inventory_service.get_product(id)
    except ProductNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get product: {str(e)}"
        )


@router.delete(
    "/delete_product",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=storekeeper_only,
)
def delete_product(
    id: UUID,
    inventory_service: InventoryService = Depends(get_inventory_service),
):
    try:
        return inventory_service.delete(id)
    except ProductNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete product: {str(e)}"
        )