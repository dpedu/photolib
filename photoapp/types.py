from sqlalchemy import Column, Integer, String, DateTime, Unicode, DECIMAL, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

import uuid


Base = declarative_base()


class PhotoSet(Base):
    __tablename__ = 'photos'

    id = Column(Integer, primary_key=True)
    uuid = Column(Unicode, default=lambda: str(uuid.uuid4()))
    date = Column(DateTime)
    lat = Column(DECIMAL(precision=11))
    lon = Column(DECIMAL(precision=11))

    files = relationship("Photo", back_populates="set")


class Photo(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    set_id = Column(Integer, ForeignKey("photos.id"))
    uuid = Column(Unicode, default=lambda: str(uuid.uuid4()))

    set = relationship("PhotoSet", back_populates="files", foreign_keys=[set_id])

    size = Column(Integer)
    width = Column(Integer)
    height = Column(Integer)
    hash = Column(String(length=64), unique=True)
    path = Column(Unicode)
    format = Column(String(length=64))  # TODO how long can a mime string be
