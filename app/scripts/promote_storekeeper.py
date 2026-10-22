"""
Promote an existing account to STOREKEEPER.

Use this to create the FIRST storekeeper (after that, a storekeeper can promote
others through POST /auth/promote). The person must already have registered
through the normal register page.

Run from the project root (the folder that contains main.py):

    python -m app.scripts.promote_storekeeper someone@example.com
"""
import sys

from sqlmodel import Session

from app.config.database import engine
from app.exception import UserNotFoundException
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python -m app.scripts.promote_storekeeper <email>")
        return 2

    email = argv[1].strip()

    with Session(engine) as session:
        service = AuthService(UserRepository(session))

        try:
            user = service.promote_to_storekeeper(email)
        except UserNotFoundException:
            print(f"No account found for {email}. Ask them to register first.")
            return 1

    print(f"{user.email} is now a {user.role.value}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))