"""
Users Table.

Map certificate identities and authorization flags to user records. Provide
lookup helpers and a read-only API schema including the derived display name.
"""
from __future__ import annotations

import logging
from typing import Self, overload

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import TEXT, Boolean, Integer, select
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Mapped, mapped_column

# from sqlmodel import Field, SQLModel
from ..registry import managed_session
from ..SQLTableBase import SQLTableBase


class User(BaseModel):
    """
    JSON-serialisable schema for a Users row.

    Attributes:
        id (int): User record identifier.
        dn (str): Certificate distinguished name.
        ca (str): Issuing certificate authority.
        email (str): Registered email address.
        suspended (bool): Whether access is suspended.
        admin (bool): Whether administrative access is granted.
        name (str): Display name derived from the distinguished name.
    """
    model_config = ConfigDict(from_attributes=True, validate_assignment=True)

    id: int = Field(frozen=True)
    dn: str = Field(frozen=True)
    ca: str = Field(frozen=True)
    email: str = Field(frozen=True)
    suspended: bool = Field(frozen=True)
    admin: bool = Field(frozen=True)
    name: str = Field(frozen=True)  # mainly used when converting ORM objects to pydantic as all attributes are read. Could have as a pydantic computed field but the code would duplicate that in the ORM model.


class Users(SQLTableBase):
    """
    Users SQL Table.

    Store certificate identities and access flags. Equality and hashing use
    the distinguished name and certificate authority rather than the row ID.
    """
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # pylint: disable=invalid-name
    dn: Mapped[str] = mapped_column(TEXT, nullable=False)  # pylint: disable=invalid-name
    ca: Mapped[str] = mapped_column(TEXT, nullable=False)  # pylint: disable=invalid-name
    email: Mapped[str] = mapped_column(TEXT, nullable=False)
    suspended: Mapped[bool] = mapped_column(Boolean, nullable=False)
    admin: Mapped[bool] = mapped_column(Boolean, nullable=False)
    logger = logging.getLogger(__name__).getChild(__qualname__)

    @property
    def name(self) -> str:
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
        """
        hash.

        Returns:
            int: Hash of the user certificate DN and CA pair.
        """
        return hash((self.dn, self.ca))

    def __eq__(self, other: Self) -> bool:
        """
        Equality check.

        Args:
            other: User record to compare by certificate DN and CA.

        Returns:
            bool: True when both users have the same DN and CA.
        """
        return (self.dn, self.ca) == (other.dn, other.ca)

    def update(self):
        """
        Update the DB record from this Users object.

        Merge this instance into a managed transaction. Changes commit on
        success; database failures roll back and propagate to the caller.
        """
        with managed_session() as session:
            session.merge(self)

    @overload
    @classmethod
    def get_users(cls) -> list[Users]:
        """
        Retrieve all registered users.

        Returns:
            list[Users]: All user records, or an empty list.
        """
        ...

    @overload
    @classmethod
    def get_users(cls, *, user_id: int) -> Users:
        """
        Retrieve one registered user by identifier.

        Args:
            user_id (int): User record identifier.

        Returns:
            Users: The uniquely matching user.

        Raises:
            NoResultFound: If no user matches.
            MultipleResultsFound: If multiple users match.
        """
        ...

    @classmethod
    def get_users(cls, user_id: int | None = None) -> Users | list[Users]:
        """
        Get users from database.

        Gets all users in database or explicitly those with a given user_id.

        Args:
            user_id (int | None): User id to extract. None gives all users (default None)

        Raises:
            TypeError: If user_id is not an int (or convertable to int).
            NoResultFound: If no user matches the given criteria when a single user_id is provided.
            MultipleResultsFound: If multiple users match the given criteria when a single user_id is provided.

        Returns:
            Users | list[Users]: The user/users pulled from the database

        """
        if user_id is not None:
            try:
                user_id = int(user_id)
            except ValueError as err:
                cls.logger.error("User id: %r should be of type int (or convertable to int)", user_id)
                raise TypeError(f"User id: {user_id!r} should be of type int (or convertable to int)") from err

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
