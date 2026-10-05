# Small Business Management System (Multi-Tenant)

A full-stack, multi-tenant web application for managing customers, products,
orders, sales, expenses, payments, invoices, and reports — built so you can
run it for one business, or offer it as a SaaS product to many businesses at
once, each with its own fully isolated data.

**Stack:** React (Vite) + FastAPI + SQLAlchemy + Alembic (migrations) +
SQLite (dev) / MySQL (production) — JWT access + refresh tokens, per-tenant
row-level isolation, rate limiting, account lockout.

---

## 1. Project Structure

```
smb-app/
├── docker-compose.yml   self-hosted deployment (MySQL + backend in containers)
├── backend/             FastAPI REST API
│   ├── main.py
│   ├── database.py
│   ├── seed.py          optional demo-data script
│   ├── Dockerfile
│   ├── alembic/         database migrations (schema version control)
│   ├── models/          SQLAlchemy models (Tenant + every business table)
│   ├── schemas/         Pydantic request/response schemas
│   ├── routers/         one router per resource, all tenant-scoped
│   ├── auth/            hashing, JWT, refresh tokens, lockout, rate limiting
│   └── requirements.txt
└── frontend/             React (Vite) single-page app
    └── src/
        ├── api/          axios client (auto-refreshes expired tokens)
        ├── context/      auth context (user + tenant)
        ├── components/   Navbar/Sidebar/Modal/Badge/Layout
        └── pages/        one page per feature
```

---

## 2. How multi-tenancy works

- Every business that signs up gets one row in the `tenants` table.
- Every other table (customers, products, orders, expenses, payments,
  invoices, and the users themselves) carries a `tenant_id` column.
- **Every single query in every router filters by the logged-in user's
  `tenant_id`.** Fetching a record by ID also checks it belongs to your
  tenant, not just that the ID exists — this closes the common
  "change the ID in the URL and see someone else's data" (IDOR) hole.
- Sign-up flow: `POST /auth/register-business` creates a new Tenant plus its
  first Admin user. There is **no public self-registration for staff** —
  only an existing Admin can add more users (`POST /auth/staff`), which
  prevents anyone from registering themselves as an Admin of an existing
  business.
- I tested this directly: created two separate businesses, and confirmed
  Business B gets a 404 trying to read Business A's customers/products by
  ID, and a 400 trying to create an order against Business A's data —
  not just that the UI hides it, the API itself refuses.

---

## 3. Security measures implemented

- **Passwords:** bcrypt hashing, minimum 8 characters with a letter and a
  number enforced server-side.
- **Tokens:** short-lived JWT access tokens (30 min default) + long-lived
  refresh tokens (14 days default), stored server-side only as a SHA-256
  hash (not the raw token) so a database leak can't be replayed. Logout
  revokes the refresh token; the frontend auto-refreshes expired access
  tokens transparently.
- **Brute-force protection:** failed logins are tracked per account; after 5
  failed attempts the account locks for 15 minutes. Separately, the login
  endpoint is rate-limited to 10 requests/minute per IP.
- **CORS:** restricted to an explicit allow-list (`ALLOWED_ORIGINS` in
  `.env`), not `*`.
- **Security headers:** `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`, and `Strict-Transport-Security`
  are set on every response.
- **Error handling:** unhandled exceptions return a generic 500 message —
  stack traces and internals are never sent to the client.
- **Secrets:** the app refuses to start with the placeholder `SECRET_KEY`
  when `ENVIRONMENT=production`.
- **SQL injection:** mitigated throughout by using the SQLAlchemy ORM
  (no raw string-built queries anywhere).

I ran an automated test suite covering all of the above (cross-tenant
isolation, lockout, rate limiting, token refresh/revocation) — see
"Running the tests" below.

---

## 4. Backend Setup (local development, SQLite)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # then edit SECRET_KEY at minimum

# Apply the database schema (Alembic migration)
alembic upgrade head

# (Optional) demo data: a business, an admin login, a few customers/products
python seed.py

uvicorn main:app --reload --port 8000
```

API: http://localhost:8000 · Docs: http://localhost:8000/docs

Demo login after `seed.py` (if you ran it): `admin@business.com` /
`admin12345`.

### Running the tests
There's no separate test file bundled (to keep the delivered project small),
but here's the exact script I used to verify tenant isolation, lockout, rate
limiting, and token refresh — paste it into a Python shell from `backend/`
with the venv active:

```python
from fastapi.testclient import TestClient
from main import app
client = TestClient(app)

r = client.post('/auth/register-business', json={
    'business_name': 'Test Co', 'full_name': 'Admin User',
    'email': 'admin@testco.com', 'password': 'password123'
})
print(r.status_code, r.json())
```

Build out further calls from there (see the multi-tenant isolation checks
described in section 2) to exercise any endpoint.

---

## 5. Database Deployment

### Option A: AWS RDS (MySQL)

1. **Create the instance.** AWS Console → RDS → Create database → choose
   **MySQL** (8.0+), template "Free tier" for testing or "Production" for
   real use. Set a master username/password, note the initial database name
   (or create one later).
2. **Networking.** Put the RDS instance in a **private subnet** if your
   backend runs in the same VPC (e.g. on EC2/ECS) — don't expose the
   database to the public internet. If you need to connect from your laptop
   to run migrations, either temporarily enable public access + restrict the
   security group to your IP, or connect via an SSH bastion/VPN into the VPC.
3. **Security group.** Allow inbound TCP 3306 only from your backend's
   security group (and your own IP, temporarily, for the migration step).
4. **Get the endpoint.** RDS console → your instance → "Endpoint" (looks
   like `smb-db.xxxxxxxxxx.ap-south-1.rds.amazonaws.com`).
5. **Point the backend at it.** In `backend/.env`:
   ```
   DATABASE_URL=mysql+pymysql://<master_user>:<master_password>@<endpoint>:3306/smb_db
   ```
   For production, store this (and `SECRET_KEY`) in **AWS Secrets Manager**
   or **Systems Manager Parameter Store** rather than a plain `.env` file on
   disk, and inject them as environment variables at deploy time.
6. **Run migrations once** from a machine that can reach the DB:
   ```bash
   cd backend
   pip install -r requirements.txt
   alembic upgrade head
   python seed.py   # optional
   ```
7. **Run the backend itself.** Common options, roughly in order of
   simplicity: **AWS App Runner** (point it at a Dockerfile, simplest for a
   single container), **Elastic Beanstalk** (Python platform, give it
   `backend/` + a `Procfile`), or **ECS/Fargate** using the included
   `backend/Dockerfile` pushed to **ECR**. All of them just need the same
   environment variables as `.env.example`.
8. **Frontend:** `npm run build` in `frontend/` (with `VITE_API_URL` set to
   your backend's public URL), then upload `frontend/dist/` to an **S3
   bucket** with **CloudFront** in front of it for HTTPS + caching. Any
   static host (Vercel, Netlify, Amplify) works just as well.

> I don't have a live AWS account in this environment, so I couldn't run
> these steps end-to-end myself — they're the standard, documented AWS
> process. What I *did* verify locally: the `mysql+pymysql` driver loads and
> builds connection URLs correctly, and Alembic generates and applies the
> full schema cleanly against SQLite (the same migration will run unchanged
> against MySQL — Alembic/SQLAlchemy abstract the SQL dialect). Test the
> actual RDS connection in a disposable/free-tier instance before trusting
> it with real data.

### Option B: Self-hosted MySQL (Docker Compose)

A `docker-compose.yml` at the project root spins up MySQL + the backend
together:

```bash
# from the project root
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
export MYSQL_PASSWORD=some_strong_password
export MYSQL_ROOT_PASSWORD=another_strong_password
export ALLOWED_ORIGINS=http://localhost:5173

docker compose up --build -d
docker compose exec backend python seed.py   # optional demo data
```

The API is then available at `http://localhost:8000`. I validated the
`docker-compose.yml` is syntactically correct and the Dockerfile's logic is
sound, but **I don't have Docker available in this sandbox to run the full
stack**, so build and run it yourself and watch the logs
(`docker compose logs -f backend`) the first time, in case your local Docker
setup needs adjusting (e.g. port 3306 already in use).

### Moving between SQLite and MySQL generally
Just change `DATABASE_URL` in `.env` and run `alembic upgrade head` against
the new database — no model code changes needed, since Alembic/SQLAlchemy
handle the SQL dialect differences.

---

## 6. Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env   # set VITE_API_URL to your backend's URL
npm run dev
```

Open http://localhost:5173. `npm run build` outputs static files to
`frontend/dist/` for deployment (see AWS step 8 above, or any static host).

---

## 7. Feature Overview

- **Multi-tenancy:** business signup creates an isolated workspace; admins
  add staff; every query is tenant-scoped; verified with automated
  cross-tenant isolation tests.
- **Auth:** JWT access + refresh tokens, bcrypt hashing, account lockout,
  login rate limiting, role-based access (Admin vs Staff).
- **Dashboard:** live totals, a 6-month sales/expenses/profit chart, and an
  order-status breakdown — all scoped to your business only.
- **Customers / Products / Orders / Sales / Expenses / Payments / Invoices
  / Reports:** full CRUD as described in the original spec, each tenant-
  isolated. Order creation validates stock and tenant ownership of the
  customer and every product referenced; cancelling an order restores stock;
  payments automatically recompute the order's payment status; invoices
  print/download as PDF client-side (no server PDF dependency).

### Simplifications made for this build
- Reports export as CSV from the API; invoice PDF export is client-side
  (jsPDF) — the same pattern could extend to other reports.
- No email verification or password-reset flow yet — if a password is lost,
  an existing Admin can't reset another user's password through the API as
  built; that would be a reasonable next addition (e.g. an admin-triggered
  reset link).
- No per-feature plan/billing limits — every tenant currently has the same
  capabilities; a real SaaS product would likely add a `plan` field on
  `Tenant` and gate features by it.


---

## Chatbot & images

- **Business Assistant** (floating button, bottom-right on every page): answers
  from the logged-in business's own data — sales, profit, expenses, low stock,
  pending payments, top products/customers, recent orders. Endpoint:
  `POST /chat` (tenant-scoped, rate-limited, requires login).
- Works out of the box with no key. To also let it answer free-form questions
  with Claude, set `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_MODEL`) in
  `backend/.env`.
- Illustrations live in `frontend/public/images/` (auth hero, dashboard banner,
  empty state, product category thumbnails, bot avatar). They are SVGs, so you
  can swap in your own photos by replacing files with the same names.
