import argparse
from photoapp.library import PhotoLibrary
from photoapp.image import get_hash
from photoapp.types import Photo
import os


def validate_all(library):

    total = 0
    s = library.session()
    for item in s.query(Photo).order_by(Photo.date).all():
        assert item.hash == get_hash(os.path.join(library.path, item.path))
        print("ok ", item.path)
        total += 1
    print(total, "images verified")


def main():
    parser = argparse.ArgumentParser(description="Library verification tool")
    parser.parse_args()
    library = PhotoLibrary("photos.db", "./library/")
    validate_all(library)


if __name__ == '__main__':
    main()
