from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.config.cors import get_allowed_origins
from app.config.database import create_db_and_tables
from app.routers.auth_router import router as auth_router
from app.routers.inventory_router import router as inventory_router
from app.routers.sales_router import router as sales_router


from app.models.product import Product
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem, OrderStatus
from app.models.user import User
from app.routers.cart_router import router as cart_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(inventory_router)
app.include_router(sales_router)
app.include_router(cart_router)