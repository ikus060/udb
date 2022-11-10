from sqlalchemy import *
from sqlalchemy.orm import *
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


@event.listens_for(Engine, 'connect')
def _set_sqlite_journal_mode_wal(connection, connection_record):
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


class A(Base):
    __tablename__ = 'a'
    id = Column(Integer(), primary_key=True)
    name = Column(String(80))


class B(Base):
    __tablename__ = 'b'
    id = Column(Integer(), primary_key=True)
    c_id = Column(Integer, nullable=False)
    a_id = Column(Integer, nullable=False)
    value = Column(String, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            [
                c_id,
                a_id,
            ],
            ["c.id", "c.a_id"],
            onupdate="CASCADE",
        ),
        {},
    )

    def __init__(self, value=value):
        self.value = value


class C(Base):
    __tablename__ = 'c'
    id = Column(Integer(), primary_key=True)
    name = Column(String(80))
    a_id = Column(Integer, ForeignKey("a.id"), nullable=False)
    a = relationship(A)
    b = relationship(
        "B",
        lazy=False,
        cascade="all, delete-orphan",
    )
    values = association_proxy("b", "value")


Index('c_index', C.id, C.a_id, unique=True)

e = create_engine("sqlite://", echo=True)
Base.metadata.create_all(e)

session = Session(e)

a1 = A(name='default1')
a2 = A(name='default2')
session.add(a1)
session.add(a2)
session.commit()

c = C(name='test', a=a1, values=['value1', 'value2'])
session.add(c)
session.commit()

c.a = a2

assert c.values == ['value1', 'value2']
