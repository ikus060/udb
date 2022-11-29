from sqlalchemy import Column, Integer, String, ForeignKey, Computed
from sqlalchemy.orm import Session, relationship
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import object_session
from sqlalchemy.orm import validates

Base = declarative_base()


@event.listens_for(Engine, 'connect')
def enable_sqlite_foreign_keys(connection, connection_record):
    """
    Enable Foreign key for SQLite
    """
    if 'sqlite3' in str(connection.__class__):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


class Person(Base):
    __tablename__ = 'person'
    id = Column(Integer(), primary_key=True)
    firstname = Column(String(80))
    lastname = Column(String(80))
    fullname = Column(String, Computed(firstname + " " + lastname))

    @validates('fullname')
    def discard_fullname(self, key, value):
        return None


e = create_engine("sqlite://", echo=True)
Base.metadata.create_all(e)

session = Session(e)


frank = Person(firstname='Frank', lastname="Gibson")
frank.fullname = 'Frank Gibson'
session.add_all([frank])
session.commit()
