import argparse
from photoapp.library import PhotoLibrary
from photoapp.types import PhotoSet
from datetime import timedelta


def set_offset(library, uuid, offset):
    s = library.session()
    photo = s.query(PhotoSet).filter(PhotoSet.uuid == uuid).first()
    print("Original date: {}".format(photo.date))
    photo.date_offset = offset
    photo.date = photo.date_real + timedelta(minutes=offset)
    print("New date:      {}".format(photo.date))
    s.commit()


def main():
    parser = argparse.ArgumentParser(description="Photo date offset manipulation tool")
    parser.add_argument("-u", "--uuid", required=True, help="photo uuid")
    parser.add_argument("-o", "--offset", required=True, type=int, help="offset in minutes")
    args = parser.parse_args()
    library = PhotoLibrary("photos.db", "./library/", "./cache/")
    set_offset(library, args.uuid, args.offset)


if __name__ == '__main__':
    main()
