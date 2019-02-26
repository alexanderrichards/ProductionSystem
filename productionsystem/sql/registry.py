"""SQLAlchemy global session registry."""
import logging
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from productionsystem.singleton import singleton

from .SQLTableBase import SQLTableBase


@singleton
class SessionRegistry(scoped_session):
    """
    Singleton version of SQLAlchemy's scoped_session.

    This avoids the need to make the scoped_session (session registry) global
    """

    def __init__(self, url):
        """Initialisation."""
        # recycle based on (prob don't need pessimistic ping same link but above.):
        #   https://docs.sqlalchemy.org/en/latest/core/pooling.html#setting-pool-recycle
        engine = create_engine(url, pool_pre_ping=True)  # 2 hours
        SQLTableBase.metadata.create_all(bind=engine)
        super(SessionRegistry, self).__init__(sessionmaker(engine))
        self._logger = logging.getLogger(__name__)


@contextmanager
def managed_session():
    """Transactional scoped DB session context."""
    logger = logging.getLogger(__name__)
    session_registry = SessionRegistry.get_instance()  # pylint: disable=no-member
    try:
        yield session_registry()
        session_registry.commit()
        logger.debug("DB transaction committed.")
    except:  # pylint: disable=bare-except
        logger.exception("Problem with DB session, rolling back.")
        session_registry.rollback()
        raise
    finally:
        session_registry.remove()
