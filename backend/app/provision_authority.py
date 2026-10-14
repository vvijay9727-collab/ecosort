import getpass
import re

from sqlalchemy import inspect, select

from app.auth import hash_password
from app.database import SessionLocal, engine
from app.models import Base, User


def main() -> None:
    Base.metadata.create_all(bind=engine)
    user_columns = {
        column["name"] for column in inspect(engine).get_columns("users")
    }
    if "password_hash" not in user_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN password_hash VARCHAR(256)"
            )
    name = input("Authority full name: ").strip()
    email = input("Authority email: ").strip().lower()
    password = getpass.getpass("Password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")

    if not name or len(name) > 150:
        raise SystemExit("Name must contain 1-150 characters.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 320:
        raise SystemExit("Enter a valid email address.")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    with SessionLocal.begin() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None:
            raise SystemExit("An account with that email already exists.")
        db.add(
            User(
                email=email,
                full_name=name,
                role="authority",
                password_hash=hash_password(password),
            )
        )
    print(f"Municipal authority account provisioned for {email}.")


if __name__ == "__main__":
    main()
