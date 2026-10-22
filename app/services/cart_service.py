from uuid import UUID

from app.models.cart import Cart, CartItem, CreateCart
from app.repositories.cart_repository import CartRepository
from app.repositories.product_repository import ProductRepository


class CartService:
    def __init__(self, repository: CartRepository, product_repository: ProductRepository):
        self.repository = repository
        self.product_repository = product_repository

    def add_item_to_cart(self, customer_id: UUID, payload: CreateCart) -> Cart:
        cart = self.repository.get_or_create_for_customer(customer_id)
        product = self.product_repository.find_by_id(payload.product_id)

        if product is None:
            raise ValueError("Product does not exist")

        if product.quantity < payload.quantity:
            raise ValueError(f"'{product.name}' does not have enough stock")

        existing_item = self.repository.find_item_by_product(cart.id, payload.product_id)

        if existing_item is not None:
            existing_item.quantity = existing_item.quantity + payload.quantity
            self.repository.add_item(existing_item)
        else:
            new_item = CartItem(
                cart_id=cart.id,
                product_id=payload.product_id,
                quantity=payload.quantity,
                product_price=product.price,
            )
            self.repository.add_item(new_item)

        return self.get_cart(customer_id)

    def get_cart(self, customer_id: UUID) -> Cart:
        cart = self.repository.get_or_create_for_customer(customer_id)
        cart.items = self.repository.get_items(cart.id)
        return cart

    def remove_item(self, customer_id: UUID, cart_item_id: UUID) -> Cart:
        cart = self.repository.get_or_create_for_customer(customer_id)
        item = self.repository.get_item(cart_item_id)

        if item is None or item.cart_id != cart.id:
            raise ValueError("This item is not in your cart")

        self.repository.delete_item(cart_item_id)
        return self.get_cart(customer_id)

    def clear_cart(self, customer_id: UUID) -> None:
        cart = self.repository.find_cart_by_id(customer_id)

        if cart is None:
            return

        self.repository.clear_cart(cart.id)