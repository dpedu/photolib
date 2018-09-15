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
    date, gps, dimensions, orientation = get_exif_data(fpath)

    if date is None:
        import pdb
        pdb.set_trace()
        raise Exception("fuk")

    # gps is set to 0,0 if unavailable
    lat, lon = gps or [0, 0]
    dimensions = dimensions or (0, 0)
    mime = magic.from_file(fpath, mime=True)
    size = os.path.getsize(fpath)

    photo = Photo(hash=get_hash(fpath), path=fpath, format=mime, size=size,
                  width=dimensions[0], height=dimensions[1], orientation=orientation)
    return PhotoSet(date=date, date_real=date, lat=lat, lon=lon, files=[photo])


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
    Return a (datetime, (decimal, decimal), (width, height), rotation) tuple describing the photo's exif date and gps coordinates
    """
    img = Image.open(path)

    datestr = None
    gpsinfo = None
    dateinfo = None
    orientationinfo = 0
    sizeinfo = (img.width, img.height)

    if img.format in ["JPEG", "PNG", "GIF"]:
        if hasattr(img, "_getexif"):
            exif_data = img._getexif()
            if exif_data:
                exif = {
                    ExifTags.TAGS[k]: v
                    for k, v in exif_data.items()
                    if k in ExifTags.TAGS
                }
                acceptable = ["DateTime", "DateTimeOriginal", "DateTimeDigitized"]
                for key in acceptable:
                    if key in exif:
                        datestr = exif[key]
                        continue

                if datestr:
                    if not datestr.startswith("0000"):  # Weed out some known bad cases
                        try:
                            dateinfo = datetime.strptime(datestr, "%Y:%m:%d %H:%M:%S")
                        except ValueError:
                            dateinfo = datetime.strptime(datestr, "%Y:%m:%d:%H:%M:%S")

                orien = exif.get("Orientation")
                if orien:
                    orientationinfo = {0: 0, 8: 1, 3: 2, 6: 3}.get(int(orien), 0)

                gps = exif.get("GPSInfo")
                if gps and 1 in gps and 2 in gps and 3 in gps and 4 in gps:
                    # see https://gis.stackexchange.com/a/273402
                    gps_y = round(hms_to_decimal(rational64u_to_hms(gps[2])), 8)
                    gps_x = round(hms_to_decimal(rational64u_to_hms(gps[4])), 8)
                    if gps[1] == 'S':
                        gps_y *= -1
                    if gps[3] == 'W':
                        gps_x *= -1
                    gpsinfo = (gps_y, gps_x)

    if dateinfo is None:
        dateinfo = get_mtime(path)

    return dateinfo, gpsinfo, sizeinfo, orientationinfo


def rational64u_to_hms(values):
    return [Decimal(values[0][0]) / Decimal(values[0][1]),
            Decimal(values[1][0]) / Decimal(values[1][1]),
            Decimal(values[2][0]) / Decimal(values[2][1])]


def hms_to_decimal(values):
    return values[0] + values[1] / 60 + values[2] / 3600


def main():
    print(get_exif_data("library/2018/9/8/MMwo4hr.jpg"))
