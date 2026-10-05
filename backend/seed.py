"""
Seed the database with a demo business (tenant), an admin account, and a few
sample records, so the app looks realistic the first time you open it.

Run with:  python seed.py
(Run `alembic upgrade head` first if you haven't already - see README.)
"""
from database import SessionLocal
from models.models import Tenant, User, UserRole, Customer, Product
from auth.auth_utils import hash_password

db = SessionLocal()

tenant = db.query(Tenant).filter(Tenant.slug == "demo-business").first()
if not tenant:
    tenant = Tenant(business_name="Demo Business", slug="demo-business")
    db.add(tenant)
    db.flush()
    print("Created demo tenant -> slug: demo-business")

if not db.query(User).filter(User.email == "admin@business.com").first():
    db.add(User(
        tenant_id=tenant.id,
        full_name="Admin",
        email="admin@business.com",
        hashed_password=hash_password("admin12345"),
        role=UserRole.ADMIN,
    ))
    print("Created admin account -> email: admin@business.com  password: admin12345")

if db.query(Customer).filter(Customer.tenant_id == tenant.id).count() == 0:
    db.add_all([
        Customer(tenant_id=tenant.id, name="Ravi Kumar", phone="9876543210", email="ravi@example.com", address="Chennai, TN"),
        Customer(tenant_id=tenant.id, name="Priya Sharma", phone="9123456780", email="priya@example.com", address="Mumbai, MH"),
        Customer(tenant_id=tenant.id, name="Arjun Nair", phone="9988776655", email="arjun@example.com", address="Kochi, KL"),
    ])
    print("Created 3 sample customers")

if db.query(Product).filter(Product.tenant_id == tenant.id).count() == 0:
    db.add_all([
        Product(tenant_id=tenant.id, name="Notebook (A5)", category="Stationery", price=45.0, quantity=200,
                low_stock_threshold=20, description="A5 ruled notebook, 100 pages"),
        Product(tenant_id=tenant.id, name="Ballpoint Pen (Box of 10)", category="Stationery", price=60.0,
                quantity=150, low_stock_threshold=15),
        Product(tenant_id=tenant.id, name="Office Chair", category="Furniture", price=3499.0, quantity=8,
                low_stock_threshold=3),
        Product(tenant_id=tenant.id, name="LED Desk Lamp", category="Electronics", price=899.0, quantity=4,
                low_stock_threshold=5, description="Adjustable brightness, USB powered"),
    ])
    print("Created 4 sample products")

db.commit()
db.close()
print("Seed complete.")
