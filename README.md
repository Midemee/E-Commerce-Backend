# E-Commerce API

A REST backend for a small online shop, built with **FastAPI**, **SQLModel** and **MySQL**.
Customers browse products, fill a cart and check out. Storekeepers manage the inventory.

- Token-based login (JWT) with passwords hashed using Argon2
- Role-based access control: `CUSTOMER` and `STOREKEEPER`
- One register page and one login page for everybody; storekeepers are promoted afterwards
- Cart, checkout and order cancellation with automatic stock handling
- Interactive API docs at `/docs`

## Contents

- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Creating your first storekeeper](#creating-your-first-storekeeper)
- [How access works](#how-access-works)
- [API reference](#api-reference)
- [Business rules](#business-rules)
- [Running the tests](#running-the-tests)
- [Project structure](#project-structure)
- [Deploying](#deploying)

## Tech stack

| Area | Choice |
|---|---|
| Language | Python 3.12+ |
| Framework | FastAPI, served by Uvicorn |
| Database | MySQL locally, PostgreSQL on Render, through SQLModel / SQLAlchemy (PyMySQL and psycopg2) |
| Auth | JWT (PyJWT), Argon2 password hashing (pwdlib) |
| Tests | pytest, using an in-memory SQLite database |

## Getting started

### 1. Requirements

- Python 3.12 or newer
- A running MySQL server with an empty database created for this project
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### 2. Install

With uv:

```bash
uv sync
```

Or with pip:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install .
```

### 3. Configure

Create the two `.env` files described in [Configuration](#configuration).

### 4. Run

```bash
uvicorn main:app --reload
```

The API is now at <http://127.0.0.1:8000> and the interactive docs are at <http://127.0.0.1:8000/docs>.

The tables are created automatically on startup.

### Trying it in the docs page

1. Open `/docs` and call **POST /auth/register**, then **POST /auth/login**.
2. Copy the `access_token` from the login response.
3. Click **Authorize** (top right), paste the token, and confirm.
4. Every protected endpoint now sends your token.

## Configuration

Settings come from environment variables, read from `.env` files. **Never commit these files.**
They are already listed in `.gitignore`.

**`.env`** (project root)

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Signs the login tokens. The app refuses to start without it. |
| `CORS_ORIGINS` | No | Comma-separated list of frontend addresses allowed to call the API. Defaults to `http://localhost:5500,http://127.0.0.1:5500`. `*` is rejected on purpose. |

**`app/config/.env`**

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | No | A full database address. If set, it wins over the `DB_*` values below (this is what Render provides). |
| `DB_USER` | Yes* | MySQL user |
| `DB_PASSWORD` | Yes | MySQL password |
| `DB_HOST` | Yes | MySQL host, for example `localhost` |
| `DB_PORT` | Yes | MySQL port, usually `3306` |
| `DB_NAME` | Yes* | Database name |

\* Only required when `DATABASE_URL` is not set. `DB_PORT` defaults to `3306`.

Example:

```env
# .env
SECRET_KEY=replace-with-a-long-random-string
CORS_ORIGINS=http://localhost:5173
```

```env
# app/config/.env
DB_USER=shop_user
DB_PASSWORD=change-me
DB_HOST=localhost
DB_PORT=3306
DB_NAME=ecommerce
```

Generate a strong secret key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Login tokens expire after 30 minutes.

## Creating your first storekeeper

Nobody can register as a storekeeper. Everyone registers as a customer, and a customer is promoted afterwards.

**The first storekeeper** is created from the command line. The person must already have registered through `POST /auth/register`. Run this from the project root (the folder that contains `main.py`), with your virtual environment active:

```bash
python -m app.scripts.promote_storekeeper someone@example.com
```

**After that**, any storekeeper can promote another account through `POST /auth/promote`.

The role is read from the database on every request, so a promotion takes effect immediately. The frontend should refresh its saved user (call `GET /auth/me`, or log in again) to see the new role.

## How access works

Send the token on every protected request:

```
Authorization: Bearer <access_token>
```

| Who | Can do |
|---|---|
| Anyone | Register, log in |
| Any logged-in user | See their own profile, browse products |
| Customer | Use the cart, check out, view and cancel their own orders |
| Storekeeper | Create, update and delete products, promote customers |

The server always takes the user from the token. You never send a customer id or an email to say who you are, so one customer can never touch another customer's cart or orders.

Common responses:

| Status | Meaning |
|---|---|
| 400 | The request can't be done, for example not enough stock or an empty cart |
| 401 | Missing, invalid or expired token, or wrong email or password |
| 403 | Logged in, but your role isn't allowed to do this |
| 404 | The product, order or item wasn't found |
| 409 | Conflict, such as an email that is already registered or an order that is already cancelled |
| 422 | The request body failed validation |

## API reference

Full, always-current details are at `/docs`. This is the summary.

### Auth

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/auth/register` | Public | Create a customer account |
| POST | `/auth/login` | Public | Log in, returns a token and the user |
| GET | `/auth/me` | Logged in | Current user and role |
| POST | `/auth/promote` | Storekeeper | Promote an account to storekeeper |

Register body: `{ "name": "Ada Obi", "email": "ada@example.com", "password": "at-least-8-chars" }`

Login body: `{ "email": "ada@example.com", "password": "at-least-8-chars" }`

Login response:

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": "…", "name": "Ada Obi", "email": "ada@example.com", "role": "CUSTOMER" }
}
```

Use `user.role` to decide which screens to show.

Promote body: `{ "email": "ada@example.com" }`

### Inventory

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/inventory/get_all_products` | Logged in | List all products |
| GET | `/inventory/get_product?id=<uuid>` | Logged in | One product |
| POST | `/inventory/create_product` | Storekeeper | Add a product |
| POST | `/inventory/update_product` | Storekeeper | Restock and edit a product |
| DELETE | `/inventory/delete_product?id=<uuid>` | Storekeeper | Remove a product |

Create body: `{ "name": "Mug", "description": "A ceramic mug", "price": 12.5, "quantity": 20 }`

Update body: `{ "id": "<uuid>", "name": "Mug", "description": "A ceramic mug", "price": 12.5, "quantity": 10 }`

> **Update adds stock.** The `quantity` in an update is *added* to the current stock, not used as the new total.
> Sending `10` for a product that has `10` leaves `20`. It must be greater than 0.

### Cart (customers)

| Method | Path | Purpose |
|---|---|---|
| POST | `/cart-service/add_product_to_cart` | Add a product. Body: `{ "product_id": "<uuid>", "quantity": 2 }` |
| GET | `/cart-service/find_cart` | View your cart |
| DELETE | `/cart-service/clear_items_from_cart?cart_id=<id>` | Remove one line. `cart_id` here is the **cart item's** id |
| DELETE | `/cart-service/clear_cart` | Empty the cart |

### Orders (customers)

| Method | Path | Purpose |
|---|---|---|
| POST | `/sales/orders` | Check out your cart. No request body |
| GET | `/sales/orders` | List your orders |
| GET | `/sales/orders/{order_id}` | One of your orders |
| POST | `/sales/orders/{order_id}/cancel` | Cancel an order |

## Business rules

- Adding to the cart checks stock. Cart lines always follow the product's **current** price: if the storekeeper changes a price, the cart line is updated the next time the cart is viewed or checked out, and checkout charges the new price.
- Checkout checks **every** item before changing anything. If one item is out of stock, nothing is deducted and the cart is kept so the customer can fix it.
- A successful checkout deducts stock, creates the order and empties the cart.
- Order statuses are `pending`, `paid`, `shipped`, `delivered` and `cancelled`.
- A cancelled order puts its stock back, once. Shipped, delivered and already-cancelled orders can't be cancelled.
- Asking for another customer's order returns "Order not found", so order ids can't be probed.

## Running the tests

The tests use an in-memory SQLite database, so they don't need MySQL. They do need `pytest` and `httpx`:

```bash
pip install pytest httpx        # or: uv add --dev pytest httpx
python -m pytest
```

Run this from the project root. You also need `SECRET_KEY` and the `DB_*` variables set (the `.env` files are enough).

The tests cover the repositories, services, token handling, CORS settings and the role rules on every route.

## Project structure

```
.
├── main.py                       # App setup, CORS, router registration
├── pyproject.toml
├── .env                          # SECRET_KEY, CORS_ORIGINS (not committed)
└── app/
    ├── config/
    │   ├── .env                  # Database settings (not committed)
    │   ├── database.py           # Engine and table creation
    │   ├── dependencies.py       # Database session per request
    │   └── cors.py               # Allowed frontend origins
    ├── enums/user_role.py        # CUSTOMER, STOREKEEPER
    ├── exception/                # Custom errors
    ├── models/                   # Database tables and request/response shapes
    ├── repositories/             # Database access
    ├── services/                 # Business logic
    ├── routers/                  # HTTP endpoints
    ├── security/
    │   ├── dependencies.py       # Current user and role checks
    │   ├── password.py           # Argon2 hashing
    │   └── token.py              # JWT creation
    ├── scripts/
    │   └── promote_storekeeper.py
    └── tests/
```

Each request flows through the same layers: **router** (HTTP and permissions) → **service** (rules) → **repository** (database).

## Deploying

A step-by-step guide for Render (no Docker needed) is in [DEPLOY_RENDER.md](DEPLOY_RENDER.md).

In short, on any host:

1. Set `SECRET_KEY` (new, long, random), `CORS_ORIGINS` (your frontend's `https://` address, no trailing slash), and either `DATABASE_URL` or the five `DB_*` values.
2. Install with `pip install -r requirements.txt`.
3. Start without `--reload`: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
4. Serve it over HTTPS.
5. Create the first storekeeper with the script in [Creating your first storekeeper](#creating-your-first-storekeeper).

`GET /health` returns `{"status": "ok"}` for uptime and health checks.

### Database changes

Tables are created automatically if they are missing, but existing tables are **never altered**. If you change a model after deploying, you must update the live database yourself, or add a migration tool such as Alembic.

### Known limitations

- Checkout saves the order in several steps. If the database fails in the middle of saving, stock could be deducted without an order. The common cases (out of stock, missing product) are handled safely.