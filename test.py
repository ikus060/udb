import os

os.environ['SQLALCHEMY_WARN_20'] = '1'

from sqlalchemy import Column, Integer, String, ForeignKey, Computed, func, create_engine
from sqlalchemy.orm import declared_attr, Session, declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import scoped_session, sessionmaker

try:
    from sqlalchemy.orm import DeclarativeBase

    class Base(DeclarativeBase):
        pass

except ImportError:
    Base = declarative_base()


class DnsRecord(Base):
    __tablename__ = 'dnsrecord'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=False, nullable=False)
    type = Column(String, nullable=False)
    ttl = Column(Integer, nullable=False, default=3600)
    value = Column(String, nullable=False)


engine = create_engine("sqlite://", echo=True)
Base.metadata.create_all(bind=engine)

session = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))

a1 = DnsRecord(name='foo.example.com', type='A', value='192.168.1.100')
a2 = DnsRecord(name='100.1.168.192.in-addr.arpa', type='PTR', value='foo.example.com')
session.add(a1)
session.add(a2)
session.commit()
session.expire(a1)
session.expire(a2)

query = session.query(DnsRecord).with_entities(DnsRecord.name, DnsRecord.type, DnsRecord.value)

print([r._fields for r in query.all()])
