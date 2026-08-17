from werkzeug.security import generate_password_hash
from db import get_connection, init_db

init_db()

username = input("Username: ")
password = input("Password: ")

password_hash = generate_password_hash(password)

with get_connection() as conn:
    conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash)
    )
    conn.commit()

print("User created.")