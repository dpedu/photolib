from sqlalchemy import Column, Integer, String, DateTime, Unicode, DECIMAL, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid
import enum


Base = declarative_base()


class PhotoStatus(enum.Enum):
    private = 0
    public = 1
    hidden = 2


class PhotoSet(Base):
    __tablename__ = 'photos'

    id = Column(Integer, primary_key=True)
    uuid = Column(Unicode, unique=True, default=lambda: str(uuid.uuid4()))
    date = Column(DateTime)
    date_real = Column(DateTime)
    date_offset = Column(Integer, default=0)  # minutes
    lat = Column(DECIMAL(precision=11))
    lon = Column(DECIMAL(precision=11))

    files = relationship("Photo", back_populates="set")
    tags = relationship("TagItem", back_populates="set")

    title = Column(String)
    description = Column(String)
    slug = Column(String)

    status = Column(Enum(PhotoStatus), default=PhotoStatus.private)


class Photo(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    set_id = Column(Integer, ForeignKey("photos.id"))
    uuid = Column(Unicode, unique=True, default=lambda: str(uuid.uuid4()))

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
    uuid = Column(Unicode, unique=True, default=lambda: str(uuid.uuid4()))
    created = Column(DateTime, default=lambda: datetime.now())
    modified = Column(DateTime, default=lambda: datetime.now())
    is_album = Column(Boolean, default=False)
    # slug-like short name such as "iomtrip"
    name = Column(String, unique=True)
    # longer human-format title like "Isle of Man trip"
    title = Column(String)
    # url slug like "isle-of-man-trip"
    slug = Column(String, unique=True)
    # fulltext description
    description = Column(String)

    entries = relationship("TagItem", back_populates="tag")


class TagItem(Base):
    __tablename__ = 'tag_items'

    id = Column(Integer, primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"))
    set_id = Column(Integer, ForeignKey("photos.id"))
    order = Column(Integer, default=0)

    tag = relationship("Tag", back_populates="entries", foreign_keys=[tag_id])
    set = relationship("PhotoSet", back_populates="tags", foreign_keys=[set_id])

    UniqueConstraint(tag_id, set_id)
