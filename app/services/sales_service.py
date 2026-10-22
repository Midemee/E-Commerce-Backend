from typing import List
from uuid import UUID

from app.models.order import Order, OrderItem, OrderResponse, OrderStatus
from app.repositories.order_repository import OrderRepository
from app.repositories.cart_repository import CartRepository
from app.repositories.product_repository import ProductRepository
from app.services.inventory_service import InventoryService
from app.models.product import Product
from app.models.order import Order


class OrderService:
    def __init__(self, repository: OrderRepository, cart_repository: CartRepository, product_repository: ProductRepository, inventory_service : InventoryService):
        self.repository = repository
        self.cart_repository = cart_repository
        self.product_repository = product_repository
        self.inventory_service = inventory_service

    def create_order(self, customer_id: UUID) -> OrderResponse:
        cart = self.cart_repository.get_or_create_for_customer(customer_id)
        cart_items = self.cart_repository.get_items(cart.id)

        if not cart_items:
            raise ValueError("Cannot check out an empty cart")

        total = self.inventory_service.dispense(cart_items)
        order = Order(
            customer_id=customer_id,
            total_amount=total,
            status=OrderStatus.PENDING)

        order_items = []
        for item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price_purchased=item.product_price,
            )
            order_items.append(order_item)

        saved_order = self.repository.add(order, order_items)

        self.cart_repository.clear_cart(cart.id)

        return OrderResponse.model_validate(saved_order)

    def get_order(self, customer_id: UUID, order_id: UUID) -> OrderResponse:
        order = self.repository.get(order_id)
        if order is None:
            raise ValueError("Order not found")
        if order.customer_id != customer_id:
            raise ValueError("Order not found")
        return OrderResponse.model_validate(order)

    def list_orders(self, customer_id: UUID) -> list[Order]:
        return self.repository.list_for_customer(customer_id)

    def cancel_order(self, customer_id: UUID, order_id: UUID) -> OrderResponse:
        order = self.repository.get(order_id)
        if order is None:
            raise ValueError("Order not found")
        if order.customer_id != customer_id:
            raise ValueError("Order not found")
        if order.status == OrderStatus.CANCELLED:
            raise ValueError("Order is already cancelled")
        if order.status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED):
            raise ValueError(f"Cannot cancel an order that is {order.status.value}")

        order_items = self.repository.get_items(order_id)
        for item in order_items:
            product = self.product_repository.find_by_id(item.product_id)
            if product:
                product.quantity += item.quantity
                self.product_repository.save(product)
        updated = self.repository.update_status(order_id, OrderStatus.CANCELLED)
        return OrderResponse.model_validate(updated)

    def update_status(self, order_id: UUID, new_status: OrderStatus) -> OrderResponse:
        order = self.repository.get(order_id)
        if order is None:
            raise ValueError("Order not found")
        updated = self.repository.update_status(order_id, new_status)
        return OrderResponse.model_validate(updated)