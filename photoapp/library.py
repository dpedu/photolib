import os
import sys
import traceback
from time import time
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from photoapp.types import Base, Photo, PhotoSet  # need to be loaded for orm setup
from sqlalchemy.exc import IntegrityError
from collections import defaultdict
from multiprocessing import Process
from PIL import Image, ImageOps


class PhotoLibrary(object):
    def __init__(self, db_path, lib_path):
        self.path = lib_path
        self.cache_path = "./cache"  # TODO param
        self.engine = create_engine('sqlite:///{}'.format(db_path),
                                    connect_args={'check_same_thread': False}, poolclass=StaticPool, echo=False)
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker()
        self.session.configure(bind=self.engine)
        self._failed_thumbs_cache = defaultdict(dict)

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

    def make_thumb(self, photo, style):
        """
        Create a thumbnail of the given photo, scaled/cropped to the given named style
        :return: local path to thumbnail file or None if creation failed or was blocked
        """
        # style tuples: max x, max y, rotate ok)
        # rotate ok means x and y maxes can be swapped if it fits the image's aspect ratio better
        styles = {"tiny": (80, 80, False),
                  "small": (100, 100, False),
                  "feed": (250, 250, False),
                  "preview": (1024, 768, True),
                  "big": (2048, 1536, True)}
        dest = os.path.join(self.cache_path, "thumbs", style, "{}.jpg".format(photo.uuid))
        if os.path.exists(dest):
            return os.path.abspath(dest)
        if photo.width is None:  # todo better detection of images that PIL can't open
            return None
        if photo.uuid not in self._failed_thumbs_cache[style]:
            thumb_width, thumb_height, flip_ok = styles[style]
            i_width = photo.width
            i_height = photo.height
            im_is_rotated = photo.orientation % 2 != 0 or i_height > i_width

            if im_is_rotated and flip_ok:
                thumb_width, thumb_height = thumb_height, thumb_width

            thumb_width = min(thumb_width, i_width if i_width > 0 else 999999999)  # TODO do we even have photo.width if PIL can't read the image?
            thumb_height = min(thumb_height, i_height if i_height > 0 else 999999999)  # TODO this seems bad

            p = Process(target=self.gen_thumb, args=(os.path.join(self.path, photo.path), dest, thumb_width, thumb_height, photo.orientation))
            p.start()
            p.join()
            if p.exitcode != 0:
                self._failed_thumbs_cache[style][photo.uuid] = True  # dont retry failed generations
                return None
            return os.path.abspath(dest)
        return None

    @staticmethod
    def gen_thumb(src_img, dest_img, width, height, rotation):
        try:
            start = time()
            # TODO lock around the dir creation
            os.makedirs(os.path.split(dest_img)[0], exist_ok=True)
            image = Image.open(src_img)
            image = image.rotate(90 * rotation, expand=True)
            thumb = ImageOps.fit(image, (width, height), Image.ANTIALIAS)
            thumb.save(dest_img, 'JPEG')
            print("Generated {} in {}s".format(dest_img, round(time() - start, 4)))
        except:
            traceback.print_exc()
            if os.path.exists(dest_img):
                os.unlink(dest_img)
            sys.exit(1)
