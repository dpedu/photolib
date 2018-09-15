import magic
import argparse
import traceback
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


def pprogress(done, total=None):
    print("  complete: {}{}\r".format(done, " / {} ".format(total) if total else ''), end='')


def batch_ingest(library, files):
    # group by extension
    byext = {k: [] for k in known_extensions}

    total = len(files)
    print("processing {} items".format(total))
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
        pprogress(len(photos), total)

    print("\nScanning RAWs")
    # process raws
    done = len(photos)
    for item in chain(*[byext[ext] for ext in files_raw]):
        itemmeta = Photo(hash=get_hash(item), path=item, size=os.path.getsize(item),
                         format=special_magic(item))
        fprefix = os.path.basename(item)[::-1].split(".", 1)[-1][::-1]
        fmatch = "{}.jpg".format(fprefix.lower())
        foundmatch = False
        for photo in photos:
            for fmt in photo.files[:]:
                if os.path.basename(fmt.path).lower() == fmatch:
                    foundmatch = True
                    photo.files.append(itemmeta)
                    done += 1
                    pprogress(done, total)
                    break
            if foundmatch:
                break
        if not foundmatch:
            mtime = get_mtime(item)
            photos.append(PhotoSet(date=mtime, date_real=mtime, lat=0, lon=0, files=[itemmeta]))
            done += 1
            pprogress(done, total)
        # TODO prune any xmp without an associated regular image or cr2

    print("\nScanning other files")
    # process all other formats
    for item in chain(*[byext[ext] for ext in files_video]):
        itemmeta = Photo(hash=get_hash(item), path=item, size=os.path.getsize(item),
                         format=special_magic(item))
        mtime = get_mtime(item)
        photos.append(PhotoSet(date=mtime, date_real=mtime, lat=0, lon=0, files=[itemmeta]))
        done += 1
        pprogress(done, total)

    print("\nUpdating database")
    done = 0
    total = len(photos)
    for photoset in photos:
        try:
            library.add_photoset(photoset)
            pprogress(done, total)
            done += 1
        except:
            traceback.print_exc()
            pass
    print("\nUpdate complete")


def special_magic(fpath):
    if fpath.split(".")[-1].lower() == "xmp":
        return "application/octet-stream-xmp"
    else:
        return magic.from_file(fpath, mime=True)


def main():
    parser = argparse.ArgumentParser(description="Library ingestion tool")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()

    library = PhotoLibrary("photos.db", "./library/")

    batch_ingest(library, args.files)


if __name__ == '__main__':
    main()
