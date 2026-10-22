"""Print a bcrypt hash to set as ADMIN_PASSWORD_HASH in the environment."""
from getpass import getpass

from app.utils.security import hash_password


def main():
    password = getpass("New admin password (minimum 12 characters): ")
    if len(password) < 12:
        raise SystemExit("Use at least 12 characters.")
    confirm = getpass("Confirm admin password: ")
    if password != confirm:
        raise SystemExit("Passwords did not match.")
    print(hash_password(password))


if __name__ == "__main__":
    main()
