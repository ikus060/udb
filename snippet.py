from sqlalchemy import create_engine, Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.event import listen

Base = declarative_base()

association_table = Table('association', Base.metadata,
    Column('left_id', Integer, ForeignKey('left.id')),
    Column('right_id', Integer, ForeignKey('right.id'))
)

class Left(Base):
    __tablename__ = 'left'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    rights = relationship('Right', secondary=association_table, back_populates='lefts')

class Right(Base):
    __tablename__ = 'right'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    lefts = relationship('Left', secondary=association_table, back_populates='rights')

def after_insert_listener(mapper, connection, target):
    print(f"After insert into association table: {target}")

listen(association_table, 'after_insert', after_insert_listener)

# Example usage
engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
session = Session(engine)

left_obj = Left(name='Left Object')
right_obj = Right(name='Right Object')

session.add(left_obj)
session.add(right_obj)
session.commit()

