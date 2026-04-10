"""
Seed all 4 databases with identical data.
Uses direct PostgreSQL connections (psycopg) — framework-agnostic.

Usage:
    python seed_all.py
"""

import random
import psycopg
from psycopg.rows import dict_row

DATABASES = {
    "django":   "postgresql://app:app@localhost:5433/app",
    "fastapi":  "postgresql://postgres:postgres@localhost:5436/fastapi_db",
    "litestar": "postgresql://postgres:postgres@localhost:5434/litestar_db",
    "robyn":    "postgresql://postgres:postgres@localhost:5435/robyn_db",
}

NUM_USERS = 1000
MIN_ORDERS = 5
MAX_ORDERS = 10

# Фиксированный seed для воспроизводимости — все 4 БД получат одинаковые данные
random.seed(42)


def generate_data():
    """Генерируем данные один раз, потом вставляем в каждую БД."""
    users = []
    for i in range(NUM_USERS):
        users.append({
            "email": f"user{i}@test.com",
            "name": f"User {i}",
        })

    orders = []
    for user_idx in range(NUM_USERS):
        num_orders = random.randint(MIN_ORDERS, MAX_ORDERS)
        for _ in range(num_orders):
            orders.append({
                "user_idx": user_idx,
                "total_price": round(random.uniform(10, 500), 2),
            })

    return users, orders


def ensure_tables(conn):
    """Создаём таблицы если их нет (для FastAPI/Litestar/Robyn)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            total_price NUMERIC(12, 2) NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS ix_orders_user_id ON orders (user_id)
    """)
    conn.commit()


def seed_database(name, dsn, users, orders):
    print(f"  {name}: connecting to {dsn.split('@')[1]} ...", end=" ")

    try:
        conn = psycopg.connect(dsn, row_factory=dict_row)
    except Exception as e:
        print(f"SKIP ({e})")
        return

    # Django uses app_user / app_order, others use users / orders
    # Check which tables exist
    tables = conn.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name IN ('users', 'app_user', 'app_order')
    """).fetchall()
    table_names = {t["table_name"] for t in tables}

    if "app_user" in table_names:
        # Django tables
        user_table = "app_user"
        order_table = "app_order"
    else:
        # SQLAlchemy tables (FastAPI/Litestar/Robyn)
        ensure_tables(conn)
        user_table = "users"
        order_table = "orders"

    # Clear existing data
    conn.execute(f"DELETE FROM {order_table}")
    conn.execute(f"DELETE FROM {user_table}")

    # Reset sequences
    conn.execute(f"ALTER SEQUENCE {user_table}_id_seq RESTART WITH 1")
    conn.execute(f"ALTER SEQUENCE {order_table}_id_seq RESTART WITH 1")
    conn.commit()

    # Insert users
    with conn.cursor() as cur:
        with cur.copy(f"COPY {user_table} (email, name) FROM STDIN") as copy:
            for u in users:
                copy.write_row((u["email"], u["name"]))
    conn.commit()

    # Get user IDs (in order)
    user_ids = [
        r["id"]
        for r in conn.execute(f"SELECT id FROM {user_table} ORDER BY id").fetchall()
    ]

    # Insert orders
    if "app_order" in table_names:
        # Django: app_order has created_at
        with conn.cursor() as cur:
            with cur.copy(f"COPY {order_table} (user_id, total_price, created_at) FROM STDIN") as copy:
                for o in orders:
                    copy.write_row((user_ids[o["user_idx"]], o["total_price"], "2026-01-01 00:00:00+00"))
    else:
        with conn.cursor() as cur:
            with cur.copy(f"COPY {order_table} (user_id, total_price) FROM STDIN") as copy:
                for o in orders:
                    copy.write_row((user_ids[o["user_idx"]], o["total_price"]))
    conn.commit()

    total_orders = conn.execute(f"SELECT count(*) as cnt FROM {order_table}").fetchone()["cnt"]
    conn.close()

    print(f"OK ({NUM_USERS} users, {total_orders} orders)")


def main():
    print("Generating data (seed=42) ...")
    users, orders = generate_data()
    print(f"  {len(users)} users, {len(orders)} orders")
    print()

    print("Seeding databases:")
    for name, dsn in DATABASES.items():
        seed_database(name, dsn, users, orders)

    print()
    print("Done! All databases have identical data.")


if __name__ == "__main__":
    main()
