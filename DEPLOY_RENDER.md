# Deploying: Aiven (MySQL) + Render (API)

Order matters: database first, then the API, then point the frontend at the API.

## 1. Database on Aiven

1. Sign up at <https://aiven.io> (no card needed for the free plan).
2. **Create service → MySQL → Free plan.** Name it (e.g. `ministore-db`) and create it.
3. Wait until the status is **Running** (a few minutes).
4. On the service **Overview** page copy the **Service URI**. It looks like:

   ```
   mysql://avnadmin:<password>@<host>.aivencloud.com:<port>/defaultdb?ssl-mode=REQUIRED
   ```

   Aiven uses a **non-standard port**, so keep the URI exactly as shown.
5. (Optional, more secure) Download the **CA certificate** from the same page. Open it in a text editor; you will paste its text into Render in step 2.
6. Check that the service allows connections from anywhere (Overview → *Allowed IP addresses*, default `0.0.0.0/0`). Render's free plan has no fixed IP address.

> Free Aiven services can be powered off after a period of inactivity. If the API starts failing to connect, open Aiven and power the service back on.

The app creates its tables by itself on first start. Nothing to import.

## 2. API on Render

1. Push this folder (the one containing `main.py`) to a GitHub repository. `.env` is git-ignored; check that it isn't in the repo.
2. On <https://render.com>: **New → Web Service**, pick the repo.
3. Settings:

   | Field | Value |
   |---|---|
   | Language / Runtime | Python 3 |
   | Build command | `pip install -r requirements.txt` |
   | Start command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
   | Instance type | Free |
   | Health check path (Advanced) | `/health` |

   (If the code is in a sub-folder of the repo, set **Root Directory** to it.)
4. **Environment variables:**

   | Key | Value |
   |---|---|
   | `PYTHON_VERSION` | `3.12.8` |
   | `SECRET_KEY` | a new long random string (`python -c "import secrets; print(secrets.token_urlsafe(48))"`) |
   | `DATABASE_URL` | the Aiven Service URI from step 1 |
   | `CLOUDINARY_URL` | `cloudinary://<api_key>:<api_secret>@<cloud_name>` (Master Admin key) |
   | `CORS_ORIGINS` | your frontend address, `https://…vercel.app`, **no trailing slash** (several: comma-separated) |
   | `DB_SSL_CA_PEM` | optional: the full text of Aiven's CA certificate |

   Without `DB_SSL_CA_PEM` the connection is still encrypted, but the server's certificate isn't verified.
5. Click **Create Web Service**. When the log says the service is live, open:
   - `https://<your-service>.onrender.com/health` → `{"status":"ok"}`
   - `https://<your-service>.onrender.com/docs` → the API docs

> Free Render services sleep after ~15 minutes without traffic. The first request after that takes about a minute; later ones are fast.

## 3. Connect the frontend

1. In Vercel → your project → **Settings → Environment Variables**, set `VITE_API_URL` to `https://<your-service>.onrender.com` (no trailing slash).
2. **Redeploy** the frontend. Vite bakes this value in at build time, so changing it without a redeploy does nothing.
3. Make sure `CORS_ORIGINS` on Render exactly matches the frontend address.

## 4. Create the first storekeeper

Render's free plan has no shell, so run the script from your own computer against the live database:

1. Register an account through the deployed site.
2. In the project folder, with the virtual environment active:

   ```bash
   # macOS / Linux
   DATABASE_URL='mysql://avnadmin:<password>@<host>:<port>/defaultdb?ssl-mode=REQUIRED' \
     python -m app.scripts.promote_storekeeper you@example.com

   # Windows PowerShell
   $env:DATABASE_URL='mysql://…?ssl-mode=REQUIRED'
   python -m app.scripts.promote_storekeeper you@example.com
   ```
3. Log out and back in on the site to pick up the new role.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Build fails on `pip install` | Wrong Root Directory, or `PYTHON_VERSION` not set |
| Deploy log: `Can't connect to MySQL server` / timeout | Aiven service is powered off, or the URI has the wrong host or port |
| `Database is not configured` | `DATABASE_URL` not set on Render |
| `SECRET_KEY environment variable is not configured` | `SECRET_KEY` not set |
| Browser: CORS error | `CORS_ORIGINS` doesn't match the frontend address exactly (check `https`, no trailing `/`) |
| Browser: requests go to `127.0.0.1:8001` | `VITE_API_URL` not set, or frontend not redeployed |
| Image upload gives 502 | Wrong or restricted Cloudinary key (needs Master Admin) |
| First request very slow | Render free instance waking up |
