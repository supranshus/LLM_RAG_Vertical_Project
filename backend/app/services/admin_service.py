from app.repositories.user_repo import UserRepository, UserStats


class AdminService:
    def __init__(self, users: UserRepository):
        self.users = users

    def list_users(self) -> list[UserStats]:
        return self.users.list_with_stats()
