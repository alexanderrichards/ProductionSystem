"""SQLAlchemy global session registry."""
from __future__ import annotations

import logging
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from productionsystem.singleton import singleton

from .SQLTableBase import SQLTableBase


@singleton
class SessionRegistry:
    """
    Singleton version of SQLAlchemy's session factory.

    This avoids the need to make the sessionmaker global.
    """

    def __init__(self, url):
        """Initialise."""
        # SQLAlchemy 2.0+ engine configuration with improved pool settings
        self.engine = create_engine(url,
                                    pool_pre_ping=True,  # Verify connections before using
                                    echo=False  # Set to True for SQL debugging
                                    )
        # Create all tables
        SQLTableBase.metadata.create_all(bind=self.engine)
        self._session_factory = sessionmaker(bind=self.engine,
                                             class_=Session,
                                             expire_on_commit=False)
        self._logger = logging.getLogger(__name__)

    def create_session(self):
        """Return a new session instance."""
        return self._session_factory()


@contextmanager
def managed_session():
    """Transactional scoped DB session context."""
    logger = logging.getLogger(__name__)
    # Get a new session instance
    session = SessionRegistry.get_instance().create_session()  # pylint: disable=no-member

    try:
        yield session
        session.commit()
        logger.debug("DB transaction committed.")
    except BaseException:
        logger.exception("Problem with DB session, rolling back.")
        session.rollback()
        raise
    finally:
        session.close()
