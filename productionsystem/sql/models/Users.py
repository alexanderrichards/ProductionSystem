"""Users Table."""
from __future__ import annotations

import logging
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, Integer, TEXT, Boolean, select
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
# from sqlmodel import Field, SQLModel

from ..registry import managed_session
from ..SQLTableBase import SQLTableBase


class User(BaseModel):
    """JSON-serialisable schema for a Users row."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(frozen=True)
    dn: str = Field(frozen=True)
    ca: str = Field(frozen=True)
    email: str
    suspended: bool
    admin: bool
    name: str  # mainly used when converting ORM objects to pydantic as all attributes are read. Could have as a pydantic computed field but the code would duplicate that in the ORM model.


class Users(SQLTableBase):
    """Users SQL Table."""

    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)  # pylint: disable=invalid-name
    dn = Column(TEXT, nullable=False)  # pylint: disable=invalid-name
    ca = Column(TEXT, nullable=False)  # pylint: disable=invalid-name
    email = Column(TEXT, nullable=False)
    suspended = Column(Boolean, nullable=False)
    admin = Column(Boolean, nullable=False)
    logger = logging.getLogger(__name__).getChild(__qualname__)

    @property
    def name(self):
        """
        Human-readable name from DN.

        Attempt to determine a meaningful name from a
        clients DN. Requires the DN to have already been
        converted to the more usual slash delimeted style.
        If multiple CN fields exist in the DN then the longest
        is assumend to be the desired human readable field.

        Returns:
            str: The human-readable name

        """
        cns = (token[len('CN='):] for token in self.dn.split('/')
               if token.startswith('CN='))
        return sorted(cns, key=len)[-1]

    def __hash__(self):
        """hash."""
        return hash((self.dn, self.ca))

    def __eq__(self, other):
        """Equality check."""
        return (self.dn, self.ca) == (other.dn, other.ca)

    def update(self):
        """Update the DB record from this Users object."""
        with managed_session() as session:
            session.merge(self)

    @classmethod
    def get_users(cls, user_id=None):
        """
        Get users from database.

        Gets all users in database or explicitly those with a given user_id.

        Args:
            user_id (int): User id to extract

        Returns:
            list/Users: The users/user pulled from the database

        """
        if user_id is not None:
            try:
                user_id = int(user_id)
            except ValueError:
                cls.logger.error("User id: %r should be of type int "
                                 "(or convertable to int)", user_id)
                raise

        with managed_session() as session:
            if user_id is None:
                users = session.scalars(select(cls)).all()
                return users

            try:
                user = session.scalars(
                    select(cls)
                    .where(cls.id == user_id)
                ).one()
            except NoResultFound:
                cls.logger.warning("No result found for user id: %d", user_id)
                raise
            except MultipleResultsFound:
                cls.logger.error("Multiple results found for user id: %d", user_id)
                raise
            return user
