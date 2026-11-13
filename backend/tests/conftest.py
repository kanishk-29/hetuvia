from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from app.db.session import get_engine


@pytest.fixture
def db() -> Iterator[Session]:
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()