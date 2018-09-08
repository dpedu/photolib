from datetime import datetime
from PIL import Image, ExifTags
from decimal import Decimal
from hashlib import sha256
import os
import magic
from photoapp.types import Photo, PhotoSet


def get_jpg_info(fpath):
    """
    Given the path to a jpg, return a dict describing it
    """
    date, gps = get_exif_data(fpath)

    if not date:
        # No exif date, fall back to file modification date
        date = get_mtime(fpath)

    # gps is set to 0,0 if unavailable
    lat, lon = gps or [0, 0]

    mime = magic.from_file(fpath, mime=True)

    # ps = PhotoSet

    photo = Photo(hash=get_hash(fpath), path=fpath, format=mime)
    # "fname": os.path.basename(fpath),

    return PhotoSet(date=date, lat=lat, lon=lon, files=[photo])

    # return {"date": date,
    #         "lat": lat,
    #         "lon": lon,
    #         "formats": []}


def get_mtime(fpath):
    return datetime.fromtimestamp(os.stat(fpath).st_mtime)


def get_hash(path):
    hasher = sha256()
    with open(path, 'rb') as f:
        while True:
            piece = f.read(1024 * 256)
            if not piece:
                break
            hasher.update(piece)
    return hasher.hexdigest()


def get_exif_data(path):
    """
    Return a (datetime, (decimal, decimal)) tuple describing the photo's exif date and gps coordinates
    """
    img = Image.open(path)
    if img.format != "JPEG":
        return None, None
    exif_data = img._getexif()
    if not exif_data:
        return None, None
    exif = {
        ExifTags.TAGS[k]: v
        for k, v in exif_data.items()
        if k in ExifTags.TAGS
    }
    datestr = None
    gpsinfo = None
    dateinfo = None
    acceptable = ["DateTime", "DateTimeOriginal", "DateTimeDigitized"]
    for key in acceptable:
        if key in exif:
            datestr = exif[key]
            continue

    if datestr is None:
        print(exif.keys())
        raise Exception("{} has no DateTime".format(path))  # TODO how often do we hit this
    dateinfo = datetime.strptime(datestr, "%Y:%m:%d %H:%M:%S")

    gps = exif.get("GPSInfo")
    if gps:
        # see https://gis.stackexchange.com/a/273402
        gps_y = round(hms_to_decimal(rational64u_to_hms(gps[2])), 8)
        gps_x = round(hms_to_decimal(rational64u_to_hms(gps[4])), 8)
        if gps[1] == 'S':
            gps_y *= -1
        if gps[3] == 'W':
            gps_x *= -1
        gpsinfo = (gps_y, gps_x)

    return dateinfo, gpsinfo


def rational64u_to_hms(values):
    return [Decimal(values[0][0]) / Decimal(values[0][1]),
            Decimal(values[1][0]) / Decimal(values[1][1]),
            Decimal(values[2][0]) / Decimal(values[2][1])]


def hms_to_decimal(values):
    return values[0] + values[1] / 60 + values[2] / 3600
