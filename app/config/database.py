import atexit
import os
import tempfile
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url
from sqlmodel import SQLModel, create_engine
from app.models.product import Product
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem, OrderStatus
from app.models.user import User

load_dotenv()

def _ca_file() -> str | None:
    path = os.getenv("DB_SSL_CA")
    if path:
        return path

    pem = os.getenv("DB_SSL_CA_PEM")
    if pem:
        pem = pem.replace("\\n", "\n")
        f = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
        f.write(pem)
        f.close()
        atexit.register(lambda: os.path.exists(f.name) and os.remove(f.name))
        return f.name

    return None


def _build_url() -> tuple[URL, bool]:
    raw = os.getenv("DATABASE_URL")
    if raw:
        url = make_url(raw.strip())
        url = url.set(drivername="mysql+pymysql")
        query = dict(url.query)
        mode = query.pop("ssl-mode", None) or query.pop("ssl_mode", None)
        use_ssl = str(mode).upper() in {"REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY"}
        return url.set(query=query), use_ssl

    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    name = os.getenv("DB_NAME")
    port = os.getenv("DB_PORT") or "3306"

    missing = [
        key
        for key, value in {
            "DB_USER": user,
            "DB_PASSWORD": password,
            "DB_HOST": host,
            "DB_NAME": name,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Database is not configured. Set DATABASE_URL, or all of: "
            + ", ".join(missing)
        )

    url = make_url(
        f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{name}"
    )
    use_ssl = os.getenv("DB_SSL", "").lower() in {"1", "true", "yes"}
    return url, use_ssl


DB_URL, _USE_SSL = _build_url()

_connect_args: dict = {}
_ca = _ca_file()
if _ca:
    _connect_args["ssl"] = {"ca": _ca}
elif _USE_SSL:
    _connect_args["ssl"] = {"check_hostname": False}

engine = create_engine(
    DB_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    pool_recycle=280,
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)