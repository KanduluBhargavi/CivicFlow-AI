import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def validate_production_security():
    """Reject known insecure defaults when deployed in production."""
    if os.getenv("APP_ENV", "development").lower() != "production":
        return
    secret = os.getenv("SECRET_KEY", "")
    if len(secret) < 32 or secret in {"replace-this-before-production", "regression-test-key"}:
        raise RuntimeError("Production SECRET_KEY must be a unique 32+ character secret")
    otp_pepper = os.getenv("OTP_PEPPER", "")
    if len(otp_pepper) < 32 or otp_pepper == secret:
        raise RuntimeError("Production OTP_PEPPER must be a separate unique 32+ character secret")
    if not os.getenv("ADMIN_EMAIL") or not os.getenv("ADMIN_PASSWORD_HASH", "").startswith("$2"):
        raise RuntimeError("Production ADMIN_EMAIL and a bcrypt ADMIN_PASSWORD_HASH are required")
    if os.getenv("OTP_DEV_MODE", "false").lower() == "true":
        raise RuntimeError("OTP_DEV_MODE cannot be enabled in production")
    if not os.getenv("REDIS_URL"):
        raise RuntimeError("REDIS_URL is required for shared security state in production")
    origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "").split(",") if item.strip()]
    if not origins or "*" in origins:
        raise RuntimeError("Production CORS_ORIGINS must list specific trusted origins")
    if os.getenv("POSTGRES_PASSWORD") == "change-this-password":
        raise RuntimeError("Replace the default database password before production deployment")
