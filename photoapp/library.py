import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from photoapp.types import Base, Photo, PhotoSet
from sqlalchemy.exc import IntegrityError


class PhotoLibrary(object):
    def __init__(self, db_path, lib_path):
        self.path = lib_path
        self.engine = create_engine('sqlite:///{}'.format(db_path), echo=False)
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker()
        self.session.configure(bind=self.engine)

    def add_photoset(self, photoset):
        """
        Commit a populated photoset object to the library. The paths in the photoset's file list entries will be updated
        as the file is moved to the library path.
        """

        # Create target directory
        path = os.path.join(self.path, self.get_datedir_path(photoset.date))
        os.makedirs(path, exist_ok=True)

        moves = []  # Track files moved. If the sql transaction files, we'll undo these

        for file in photoset.files:
            dest = os.path.join(path, os.path.basename(file.path))

            # Check if the name is already in use, rename new file if needed
            dupe_rename = 1
            while os.path.exists(dest):
                fname = os.path.basename(file.path).split(".")
                fname[-2] += "_{}".format(dupe_rename)
                dest = os.path.join(path, '.'.join(fname))
                dupe_rename += 1
            os.rename(file.path, dest)
            moves.append((file.path, dest))
            file.path = dest.lstrip(self.path)

        s = self.session()
        s.add(photoset)
        try:
            s.commit()
        except IntegrityError:
            # Commit failed, undo the moves
            for move in moves:
                os.rename(move[1], move[0])
            raise

    def get_datedir_path(self, date):
        """
        Return a path like 2018/3/31 given a datetime object representing the same date
        """
        return os.path.join(str(date.year), str(date.month), str(date.day))
