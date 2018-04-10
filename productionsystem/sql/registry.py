"""SQLAlchemy global session registry."""
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from productionsystem.singleton import singleton, InstantiationError

from .models import SQLTableBase

@singleton
class SessionRegistry(scoped_session):
    """
    Singleton version of SQLAlchemy's scoped_session.

    This avoids the need to make the scoped_session (session registry) global
    """
    def __init__(self, url):
        engine = create_engine(url)
        SQLTableBase.metadata.create_all(bind=engine)
        super(SessionRegistry, self).__init__(sessionmaker(engine))
        self._logger = logging.getLogger(__name__)

    def __enter__(self):
        return self()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            try:
                self.commit()
            except:
                self._logger.exception("Problem committing to DB, rolling back.")
                self.rollback()
        else:
            self._logger.exception("Problem with DB session, rolling back.")
            self.rollback()
        self.remove()


def managed_session():
    return SessionRegistry.get_instance()
