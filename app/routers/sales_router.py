from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.config.dependencies import get_session
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.cart_repository import CartRepository
from app.exception.product_not_found_exception import ProductNotFoundException
from app.exception.product_stock_exception import ProductStockException
from app.models.order import OrderResponse, Order
from app.models.user import User
from app.security.dependencies import require_customer
from app.services.sales_service import OrderService
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/sales", tags=["sales"])


def get_sales_service(session: Session = Depends(get_session)) -> OrderService:
    order_repository = OrderRepository(session)
    cart_repository = CartRepository(session)
    product_repo = ProductRepository(session)
    return OrderService(order_repository, cart_repository, product_repo, InventoryService(product_repo))

@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
        current_user: User = Depends(require_customer),
        sales_service: OrderService = Depends(get_sales_service)):
    try:
        return sales_service.create_order(current_user.id)
    except (ValueError, ProductStockException, ProductNotFoundException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/orders", response_model=List[Order])
def list_my_orders(
        current_user: User = Depends(require_customer),
        sales_service: OrderService = Depends(get_sales_service)):
    return sales_service.list_orders(current_user.id)


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(
        order_id: UUID,
        current_user: User = Depends(require_customer),
        sales_service: OrderService = Depends(get_sales_service)):
    try:
        return sales_service.get_order(current_user.id, order_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/orders/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
        order_id: UUID,
        current_user: User = Depends(require_customer),
        sales_service: OrderService = Depends(get_sales_service)):
    try:
        return sales_service.cancel_order(current_user.id, order_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))