from uuid import UUID

from app.repositories.product_repository import ProductRepository
from app.models.product import Product, AddProduct, UpdateProduct
from app.exception.product_not_found_exception import ProductNotFoundException
from app.exception.product_stock_exception import ProductStockException


class InventoryService:

    def __init__(self, repository: ProductRepository):
        self.repository = repository

    def add_product(self, payload: AddProduct) -> Product:
        new_product = Product(
            name=payload.name,
            description=payload.description,
            price=payload.price,
            quantity=payload.quantity,
            image_url=payload.image_url,
        )

        return self.repository.save(new_product)

    def restock(self, payload: UpdateProduct) -> Product:
        if payload.quantity <= 0:
            raise ProductStockException("Invalid Quantity!!!")

        saved_product = self.repository.find_by_id(payload.id)

        if saved_product is None:
            raise ProductNotFoundException(
                f"Product {payload.id} does not exist!"
            )

        saved_product.quantity += payload.quantity
        saved_product.name = payload.name
        saved_product.description = payload.description
        saved_product.price = payload.price

        if payload.image_url is not None:
            saved_product.image_url = payload.image_url

        return self.repository.save(saved_product)

    def dispense(self, cart_items) -> float:
        to_deduct = {}
        total_amount = 0.0

        for item in cart_items:
            product_id = UUID(str(item.product_id))

            product = self.repository.find_by_id(product_id)

            if product is None:
                raise ProductNotFoundException(f"Product {product_id} does not exist!")

            wanted = to_deduct.get(product.id, (product, 0))[1] + item.quantity

            if product.quantity < wanted:
                raise ProductStockException(f"{product.name} is not enough stock!!")

            to_deduct[product.id] = (product, wanted)
            total_amount += item.quantity * product.price

        for product, quantity in to_deduct.values():
            product.quantity -= quantity
            self.repository.save(product)

        return total_amount

    def delete(self, id: UUID) -> None:
        product = self.repository.find_by_id(id)

        if not product:
            raise ProductNotFoundException(f"Product {id} not found")

        self.repository.delete_product(product.id)

    def get_product(self, id: UUID) -> Product:
        product = self.repository.find_by_id(id)

        if product is None:
            raise ProductNotFoundException(f"Product {id} not found")

        return Product.model_validate(product)

    def get_all_products(self) -> list[Product]:
        return self.repository.find_all()