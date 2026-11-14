from sqlalchemy import text
from sqlalchemy.orm import Session


class HealthRepository:
    def __init__(self, session: Session):
        self.session = session

    def ping(self) -> None:
        """Raises if the database can't be reached."""
        self.session.execute(text("SELECT 1"))
