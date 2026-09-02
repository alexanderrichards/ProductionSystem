"""SQLAlchemy Base Table Module."""
from __future__ import annotations

import json
from enum import Enum
from datetime import datetime
from abc import ABCMeta
from collections.abc import Iterable
from sqlalchemy import Column
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.exc import DetachedInstanceError

__all__ = ('SQLTableBase', )


class DeclarativeABCMeta(type(DeclarativeBase), ABCMeta):
    """Combine SQLAlchemy 2 declarative attributes with abstract bases."""

class SmartColumn(Column):
    def __init__(self, *args, **kwargs):
        required = kwargs.pop('required', False)
        allowed = kwargs.pop('allowed', False)
        Column.__init__(self, *args, **kwargs)
        self._required = required
        self._allowed = required or allowed

    @property
    def required(self):
        return self._required

    @property
    def allowed(self):
        return self._allowed


class ColumnsDescriptor(object):
    """Yield the column names."""

    def __init__(self, required=False, allowed=False):
        """Initialise."""
        self._required = required
        self._allowed = allowed

    def __get__(self, obj, cls):
        """Descriptor get."""
        for column in cls.__table__.columns:
            # use getattr so works (doesnt break) on normal column as well as smart column
            if self._required and not getattr(column, 'required', False):
                continue
            if self._allowed and not getattr(column, 'allowed', False):
                continue
            yield column.name

    def __set__(self, obj, value):
        """Descriptor set."""
        raise AttributeError("Read only attribute!")


class IterableBase(Iterable):
    """
    Iterable base class.

    A base class that provides the functionality of
    being able to iterate over the instrumented attributes
    of an SQLAlchemy declarative base.
    """

    # This we can get from the class as well as instance
    # unlike property
    columns = ColumnsDescriptor()
    required_columns = ColumnsDescriptor(required=True)
    allowed_columns = ColumnsDescriptor(allowed=True)

    def __iter__(self):
        """Get an iterator over instrumented attributes."""
        for name, type_ in vars(self.__class__).items():
            if isinstance(type_, (InstrumentedAttribute, property)):
                try:
                    getattr(self, name, None)
                except DetachedInstanceError:  # This is lazy loaded and not available
                    continue
                yield name

    def __getitem__(self, item):
        """Access instrumented attributes as a dict."""
        if not hasattr(self, item):
            raise KeyError("Invalid attribute name: %s" % item)
        return getattr(self, item, None)  # None should never be needed here try deleting

    def __len__(self):
        return len(list(iter(self)))

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return id(self) == id(other)

    def jsonable_dict(self):
        """Return an easily JSON encodable object."""
        output_obj = {}
        for column in self:
            value = self[column]
            if isinstance(value, (str, int, float, bool, type(None))):
                output_obj[column] = value
            elif isinstance(value, Enum):
                output_obj[column] = value.name.capitalize()
            elif isinstance(value, datetime):
                output_obj[column] = value.isoformat(' ')
            else:
                output_obj[column] = str(value)
        return output_obj

    def to_json(self):
        """Return a JSON representation of the object."""
        return json.dumps(self.jsonable_dict())


class SQLTableBase(IterableBase, DeclarativeBase, metaclass=DeclarativeABCMeta):
    """
    Modern SQLAlchemy 2.0+ declarative base.

    Combines DeclarativeBase with IterableBase for enhanced functionality.
    """
    __abstract__ = True
