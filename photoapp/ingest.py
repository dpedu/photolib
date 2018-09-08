import magic
import argparse
from photoapp.library import PhotoLibrary
from photoapp.image import get_jpg_info, get_hash, get_mtime
from itertools import chain
from photoapp.types import Photo, PhotoSet
import os

"""
Photo sorting rules:

jpeg
    exif date
    file modification date
raw
    group with exif date of jpeg with same name
    file modification date
mov, video, or other
    modification date
"""

known_extensions = ["jpg", "png", "cr2", "xmp", "mp4", "mov"]
regular_images = ["jpg", "png"]
files_raw = ["cr2", "xmp"]
files_video = ["mp4", "mov"]


def batch_ingest(library, files):
    # group by extension
    byext = {k: [] for k in known_extensions}

    print("Pre-sorting files")
    for item in files:
        if not os.path.isfile(item):
            print("Skipping due to not a file: {}".format(item))
            continue
        extension = item.split(".")
        if len(extension) < 2:
            print("Skipping due to no extension: {}".format(item))
            continue
        extension = extension[-1].lower()
        if extension == "jpeg":
            extension = "jpg"
        if extension not in known_extensions:
            print("Skipping due to unknown extension: {}".format(item))
            continue
        byext[extension.lower()].append(item)

    print("Scanning images")
    photos = []
    # process regular images first.
    for item in chain(*[byext[ext] for ext in regular_images]):
        photos.append(get_jpg_info(item))

    print("Scanning RAWs")
    # process raws
    for item in chain(*[byext[ext] for ext in files_raw]):
        itemmeta = Photo(hash=get_hash(item), path=item, format=magic.from_file(item, mime=True))
        fprefix = os.path.basename(item)[::-1].split(".", 1)[-1][::-1]
        fmatch = "{}.jpg".format(fprefix.lower())
        foundmatch = False
        for photo in photos:
            for fmt in photo.files[:]:
                if os.path.basename(fmt.path).lower() == fmatch:
                    foundmatch = True
                    photo.files.append(itemmeta)
                    break
            if foundmatch:
                break

        if not foundmatch:
            photos.append(PhotoSet(date=get_mtime(item), lat=0, lon=0, files=[itemmeta]))

        # TODO prune any xmp without an associated regular image or cr2

    print("Scanning other files")
    # process all other formats
    for item in chain(*[byext[ext] for ext in files_video]):
        itemmeta = Photo(hash=get_hash(item), path=item, format=magic.from_file(item, mime=True))
        photos.append(PhotoSet(date=get_mtime(item), lat=0, lon=0, files=[itemmeta]))

    print("Updating database")
    for photoset in photos:
        library.add_photoset(photoset)


def main():
    parser = argparse.ArgumentParser(description="Library ingestion tool")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()

    library = PhotoLibrary("photos.db", "./library/")

    batch_ingest(library, args.files)


if __name__ == '__main__':
    main()
