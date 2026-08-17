# Copy this file to config.py and fill in real values.
# config.py is gitignored because it holds secrets (SECRET_KEY, ADMIN_PASSWORD_HASH).

DEBUG = True
DATABASE_PATH = "data/ruuvi.db"

# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY = "change-me"

ADMIN_USERNAME = "admin"

# Generate with: python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-password'))"
ADMIN_PASSWORD_HASH = "change-me"
