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

    title = Column(String)
    description = Column(String)


class Photo(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    set_id = Column(Integer, ForeignKey("photos.id"))
    uuid = Column(Unicode, default=lambda: str(uuid.uuid4()))

    set = relationship("PhotoSet", back_populates="files", foreign_keys=[set_id])

    size = Column(Integer)
    width = Column(Integer)
    height = Column(Integer)
    orientation = Column(Integer, default=0)
    hash = Column(String(length=64), unique=True)
    path = Column(Unicode)
    format = Column(String(length=64))  # TODO how long can a mime string be


class Tag(Base):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    uuid = Column(Unicode, default=lambda: str(uuid.uuid4()))
    created = Column(DateTime)
    modified = Column(DateTime)
    title = Column(String)
    slug = Column(String)
    description = Column(String)

    entries = relationship("TagItem", back_populates="tag")


class TagItem(Base):
    __tablename__ = 'tag_items'

    id = Column(Integer, primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"))

    tag = relationship("Tag", back_populates="entries", foreign_keys=[tag_id])

    item_uuid = Column(String, unique=True)
    order = Column(Integer, default=0)
