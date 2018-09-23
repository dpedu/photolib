import os
import cherrypy
import logging
from datetime import datetime, timedelta
from photoapp.library import PhotoLibrary
from photoapp.types import Photo, PhotoSet, Tag, TagItem, PhotoStatus
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import desc
from sqlalchemy import func, and_
import math
from urllib.parse import urlparse


APPROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))


def auth():
    """
    Return the currently authorized username (per request) or None
    """
    return cherrypy.session.get('authed', None)


def mime2ext(mime):
    """
    Given a mime type return the canonical file extension
    """
    return {"image/png": "png",
            "image/jpeg": "jpg",
            "image/gif": "gif",
            "application/octet-stream-xmp": "xmp",
            "image/x-canon-cr2": "cr2",
            "video/mp4": "mp4",
            "video/quicktime": "mov"}[mime]


def require_auth(func):
    """
    Decorator: raise 403 unless session is authed
    """
    def wrapped(*args, **kwargs):
        if not auth():
            raise cherrypy.HTTPError(403)
        return func(*args, **kwargs)
    return wrapped


def photo_auth_filter(query):
    """
    Sqlalchemy helper: filter the given PhotoSet query to items that match the authorized user's PhotoStatus access
    level. Currently, authed users can access ALL photos, and unauthed users can access only PhotoStatus.public
    status items.
    """
    return query.filter(PhotoSet.status == PhotoStatus.public) if not auth() else query


def slugify(words):
    return ''.join(letter for letter in '-'.join(words.lower().split())
                   if ('a' <= letter <= 'z') or ('0' <= letter <= '9') or letter == '-')


class PhotosWeb(object):
    def __init__(self, library, template_dir):
        self.library = library
        self.tpl = Environment(loader=FileSystemLoader(template_dir),
                               autoescape=select_autoescape(['html', 'xml']))
        self.tpl.filters.update(mime2ext=mime2ext,
                                basename=os.path.basename,
                                ceil=math.ceil,
                                statusstr=lambda x: str(x).split(".")[-1])

        self.thumb = ThumbnailView(self)
        self.photo = PhotoView(self)
        self.download = DownloadView(self)
        self.date = DateView(self)
        self.tag = TagView(self)
        self.album = self.tag

    def render(self, template, **kwargs):
        """
        Render a template
        """
        return self.tpl.get_template(template).render(**kwargs, **self.get_default_vars())

    def get_default_vars(self):
        """
        Return a dict containing variables expected to be on every page
        """
        s = self.session()
        # all tags / albums with photos visible under the current auth context
        tagq = s.query(Tag).join(TagItem).join(PhotoSet)
        if not auth():
            tagq = tagq.filter(PhotoSet.status == PhotoStatus.public)
        tagq = tagq.filter(Tag.is_album == False).order_by(Tag.name).all()  # pragma: manual auth

        albumq = s.query(Tag).join(TagItem).join(PhotoSet)
        if not auth():
            albumq = albumq.filter(PhotoSet.status == PhotoStatus.public)
        albumq = albumq.filter(Tag.is_album == True).order_by(Tag.name).all()  # pragma: manual auth

        ret = {
            "all_tags": tagq,
            "all_albums": albumq,
            "path": cherrypy.request.path_info,
            "auth": auth(),
            "PhotoStatus": PhotoStatus
        }
        s.close()
        return ret

    def session(self):
        """
        Get a database session
        """
        return self.library.session()

    @cherrypy.expose
    def index(self):
        """
        Home page - redirect to the photo feed
        """
        raise cherrypy.HTTPRedirect('feed', 302)

    @cherrypy.expose
    def feed(self, page=0, pgsize=25):
        """
        /feed - main photo feed - show photos sorted by date, newest first
        """
        s = self.session()
        page, pgsize = int(page), int(pgsize)
        total_sets = photo_auth_filter(s.query(func.count(PhotoSet.id))).first()[0]
        images = photo_auth_filter(s.query(PhotoSet)).order_by(PhotoSet.date.desc()). \
            offset(pgsize * page).limit(pgsize).all()
        yield self.render("feed.html", images=[i for i in images], page=page, pgsize=int(pgsize), total_sets=total_sets)

    @cherrypy.expose
    def stats(self):
        """
        /stats - show server statistics
        """
        s = self.session()
        images = photo_auth_filter(s.query(func.count(PhotoSet.uuid),
                                           func.strftime('%Y', PhotoSet.date).label('year'),
                                           func.strftime('%m', PhotoSet.date).label('month'))). \
            group_by('year', 'month').order_by(desc('year'), desc('month')).all()
        tsize = photo_auth_filter(s.query(func.sum(Photo.size)).join(PhotoSet)).scalar()  # pragma: manual auth
        yield self.render("monthly.html", images=images, tsize=tsize)

    @cherrypy.expose
    def map(self, i=None, zoom=3):
        """
        /map - show all photos on the a map, or a single point if $i is passed
        TODO using so many coordinates is slow in the browser. dedupe them somehow.
        """
        s = self.session()
        query = photo_auth_filter(s.query(PhotoSet)).filter(PhotoSet.lat != 0, PhotoSet.lon != 0)
        if i:
            query = query.filter(PhotoSet.uuid == i)
        yield self.render("map.html", images=query.all(), zoom=int(zoom))

    @cherrypy.expose
    @require_auth
    def create_tags(self, fromdate=None, uuid=None, tag=None, newtag=None, remove=None):
        """
        /create_tags - tag multiple items selected by day of photo
        :param fromdate: act upon photos taken on this day
        :param uuid: act upon a single photo with this uuid
        :param tag: target photos will have a tag specified by this uuid added
        :param remove: target photos will have the tag specified by this uuid removed
        :param newtag: new tag name to create
        """
        s = self.session()

        def get_photos():
            if fromdate:
                dt = datetime.strptime(fromdate, "%Y-%m-%d")
                dt_end = dt + timedelta(days=1)
                photos = s.query(PhotoSet).filter(and_(PhotoSet.date >= dt,
                                                       PhotoSet.date < dt_end)).order_by(PhotoSet.date)
                num_photos = s.query(func.count(PhotoSet.id)). \
                    filter(and_(PhotoSet.date >= dt, PhotoSet.date < dt_end)).order_by(PhotoSet.date).scalar()

            if uuid:
                photos = s.query(PhotoSet).filter(PhotoSet.uuid == uuid)
                num_photos = s.query(func.count(PhotoSet.id)).filter(PhotoSet.uuid == uuid).scalar()
            return photos, num_photos

        if remove:
            rmtag = s.query(Tag).filter(Tag.uuid == remove).first()
            photoq, _ = get_photos()
            for photo in photoq:
                s.query(TagItem).filter(TagItem.tag_id == rmtag.id, TagItem.set_id == photo.id).delete()
            s.commit()

        if newtag:
            s.add(Tag(title=newtag, description=newtag.capitalize(), slug=slugify(newtag)))
            s.commit()

        photos, num_photos = get_photos()

        if tag:  # Create the tag on all the photos
            tag = s.query(Tag).filter(Tag.uuid == tag).first()
            for photo in photos.all():
                if 0 == s.query(func.count(TagItem.id)).filter(TagItem.tag_id == tag.id,
                                                               TagItem.set_id == photo.id).scalar():
                    s.add(TagItem(tag_id=tag.id, set_id=photo.id))
            s.commit()

        alltags = s.query(Tag).order_by(Tag.name).all()
        yield self.render("create_tags.html", images=photos, alltags=alltags,
                          num_photos=num_photos, fromdate=fromdate, uuid=uuid)

    @cherrypy.expose
    def login(self):
        """
        /login - enable super features by logging into the app
        """
        cherrypy.session['authed'] = cherrypy.request.login
        dest = "/feed" if "Referer" not in cherrypy.request.headers \
            else urlparse(cherrypy.request.headers["Referer"]).path
        raise cherrypy.HTTPRedirect(dest, 302)

    @cherrypy.expose
    def logout(self):
        """
        /logout
        """
        cherrypy.session.clear()
        dest = "/feed" if "Referer" not in cherrypy.request.headers \
            else urlparse(cherrypy.request.headers["Referer"]).path
        raise cherrypy.HTTPRedirect(dest, 302)


@cherrypy.popargs('date')
class DateView(object):
    """
    View all the photos shot on a given date
    """
    def __init__(self, master):
        self.master = master

    @cherrypy.expose
    def index(self, date=None, page=0):
        s = self.master.session()
        if date:
            page = int(page)
            pgsize = 100
            dt = datetime.strptime(date, "%Y-%m-%d")
            dt_end = dt + timedelta(days=1)
            total_sets = photo_auth_filter(s.query(func.count(PhotoSet.id))). \
                filter(and_(PhotoSet.date >= dt, PhotoSet.date < dt_end)).first()[0]
            images = photo_auth_filter(s.query(PhotoSet)).filter(and_(PhotoSet.date >= dt,
                                                                 PhotoSet.date < dt_end)).order_by(PhotoSet.date). \
                offset(page * pgsize).limit(pgsize).all()
            yield self.master.render("date.html", page=page, pgsize=pgsize, total_sets=total_sets,
                                     images=[i for i in images], date=dt)
            return
        images = photo_auth_filter(s.query(PhotoSet, func.strftime('%Y-%m-%d',
                                   PhotoSet.date).label('gdate'),
                                   func.count('photos.id'),
                                   func.strftime('%Y', PhotoSet.date).label('year'),
                                   func.strftime('%m', PhotoSet.date).label('month'),
                                   func.strftime('%d', PhotoSet.date).label('day'))). \
            group_by('gdate').order_by(desc('year'), 'month', 'day').all()
        yield self.master.render("dates.html", images=images)


@cherrypy.popargs('item_type', 'thumb_size', 'uuid')
class ThumbnailView(object):
    """
    Generate and serve thumbnails on-demand
    """
    def __init__(self, master):
        self.master = master
        self._cp_config = {"tools.trailing_slash.on": False}

    @cherrypy.expose
    def index(self, item_type, thumb_size, uuid):
        uuid = uuid.split(".")[0]
        s = self.master.session()

        query = photo_auth_filter(s.query(Photo)).filter(Photo.set.has(uuid=uuid)) if item_type == "set" \
            else photo_auth_filter(s.query(Photo)).filter(Photo.uuid == uuid) if item_type == "one" \
            else None

        assert query

        # prefer making thumbs from jpeg to avoid loading large raws
        first = None
        best = None
        for photo in query.all():
            if first is None:
                first = photo
            if photo.format == "image/jpeg":
                best = photo
                break
        thumb_from = best or first
        if not thumb_from:
            raise Exception("404")
        # TODO some lock around calls to this based on uuid
        thumb_path = self.master.library.make_thumb(thumb_from, thumb_size)
        if thumb_path:
            return cherrypy.lib.static.serve_file(thumb_path, "image/jpeg")
        else:
            return cherrypy.lib.static.serve_file(os.path.join(APPROOT, "styles/dist/unknown.svg"), "image/svg+xml")


@cherrypy.popargs('item_type', 'uuid')
class DownloadView(object):
    """
    View original files or force-download them
    """
    def __init__(self, master):
        self.master = master
        self._cp_config = {"tools.trailing_slash.on": False}

    @cherrypy.expose
    def index(self, item_type, uuid, preview=False):
        uuid = uuid.split(".")[0]
        s = self.master.session()

        query = None if item_type == "set" \
            else photo_auth_filter(s.query(Photo)).filter(Photo.uuid == uuid) if item_type == "one" \
            else None  # TODO set download query

        item = query.first()
        extra = {}
        if not preview:
            extra.update(disposition="attachement", name=os.path.basename(item.path))
        return cherrypy.lib.static.serve_file(os.path.abspath(os.path.join(self.master.library.path, item.path)),
                                              content_type=item.format, **extra)


@cherrypy.popargs('uuid')
class PhotoView(object):
    """
    View a single photo
    """
    def __init__(self, master):
        self.master = master
        self._cp_config = {"tools.trailing_slash.on": False}

    @cherrypy.expose
    def index(self, uuid):
        uuid = uuid.split(".")[0]
        s = self.master.session()
        photo = photo_auth_filter(s.query(PhotoSet)).filter(PhotoSet.uuid == uuid).first()
        yield self.master.render("photo.html", image=photo)

    @cherrypy.expose
    @require_auth
    def op(self, uuid, op):
        s = self.master.session()
        photo = s.query(PhotoSet).filter(PhotoSet.uuid == uuid).first()
        if op == "Make public":
            photo.status = PhotoStatus.public
        elif op == "Make private":
            photo.status = PhotoStatus.private
        s.commit()
        raise cherrypy.HTTPRedirect('/photo/{}'.format(photo.uuid), 302)


@cherrypy.popargs('uuid')
class TagView(object):
    """
    View the photos associated with a single tag
    """
    def __init__(self, master):
        self.master = master
        # self._cp_config = {"tools.trailing_slash.on": False}

    @cherrypy.expose
    def index(self, uuid, page=0):
        page = int(page)
        pgsize = 100
        s = self.master.session()

        if uuid == "untagged":
            numphotos = photo_auth_filter(s.query(func.count(PhotoSet.id))). \
                filter(~PhotoSet.id.in_(s.query(TagItem.set_id))).scalar()
            photos = photo_auth_filter(s.query(PhotoSet)).filter(~PhotoSet.id.in_(s.query(TagItem.set_id))).\
                offset(page * pgsize).limit(pgsize).all()
            yield self.master.render("untagged.html", images=photos, total_items=numphotos, pgsize=pgsize, page=page)
        else:
            tag = s.query(Tag).filter(Tag.uuid == uuid).first()
            numphotos = photo_auth_filter(s.query(func.count(Tag.id)).join(TagItem).join(PhotoSet)). \
                filter(Tag.uuid == uuid).scalar()
            photos = photo_auth_filter(s.query(PhotoSet)).join(TagItem).join(Tag).filter(Tag.uuid == uuid). \
                order_by(PhotoSet.date.desc()).offset(page * pgsize).limit(pgsize).all()
            yield self.master.render("album.html", tag=tag, images=photos,
                                     total_items=numphotos, pgsize=pgsize, page=page)

    @cherrypy.expose
    @require_auth
    def op(self, uuid, op):
        """
        Perform some action on this tag
        - Promote: label this tag an album
        - Demote: label this tag as only a tag and not an album
        - Delete: remove this tag
        - Make all public: mark all photos under this tag as public
        - Make all private: mark all photos under this tag as private
        """
        s = self.master.session()
        tag = s.query(Tag).filter(Tag.uuid == uuid).first()
        if op == "Demote to tag":
            tag.is_album = 0
        elif op == "Promote to album":
            tag.is_album = 1
        elif op == "Delete tag":
            s.query(TagItem).filter(TagItem.tag_id == tag.id).delete()
            s.delete(tag)
            s.commit()
            raise cherrypy.HTTPRedirect('/', 302)
        elif op == "Make all public":
            # TODO smarter query
            for photo in s.query(PhotoSet).join(TagItem).join(Tag).filter(Tag.uuid == uuid).all():
                photo.status = PhotoStatus.public
        elif op == "Make all private":
            # TODO smarter query
            for photo in s.query(PhotoSet).join(TagItem).join(Tag).filter(Tag.uuid == uuid).all():
                photo.status = PhotoStatus.private
        else:
            raise Exception("Invalid op: '{}'".format(op))
        s.commit()
        raise cherrypy.HTTPRedirect('/tag/{}'.format(tag.uuid), 302)


def main():
    import argparse
    import signal

    parser = argparse.ArgumentParser(description="Photod photo server")

    parser.add_argument('-p', '--port', default=8080, type=int, help="tcp port to listen on")
    parser.add_argument('-l', '--library', default="./library", help="library path")
    parser.add_argument('-c', '--cache', default="./cache", help="cache path")
    parser.add_argument('-s', '--database', default="./photos.db", help="path to persistent sqlite database")
    parser.add_argument('--debug', action="store_true", help="enable development options")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.debug else logging.WARNING,
                        format="%(asctime)-15s %(levelname)-8s %(filename)s:%(lineno)d %(message)s")

    library = PhotoLibrary(args.database, args.library, args.cache)

    tpl_dir = os.path.join(APPROOT, "templates") if not args.debug else "templates"

    web = PhotosWeb(library, tpl_dir)
    web_config = {}

    def validate_password(realm, username, password):
        print("I JUST VALIDATED {}:{} ({})".format(username, password, realm))
        return True

    cherrypy.tree.mount(web, '/', {'/': web_config,
                                   '/static': {"tools.staticdir.on": True,
                                               "tools.staticdir.dir": os.path.join(APPROOT, "styles/dist")
                                               if not args.debug else os.path.abspath("styles/dist")},
                                   '/login': {'tools.auth_basic.on': True,
                                              'tools.auth_basic.realm': 'photolib',
                                              'tools.auth_basic.checkpassword': validate_password}})

    cherrypy.config.update({
        'tools.sessions.on': True,
        'tools.sessions.locking': 'explicit',
        'tools.sessions.timeout': 525600,
        'request.show_tracebacks': True,
        'server.socket_port': args.port,
        'server.thread_pool': 25,
        'server.socket_host': '0.0.0.0',
        'server.show_tracebacks': True,
        'log.screen': False,
        'engine.autoreload.on': args.debug
    })

    def signal_handler(signum, stack):
        logging.critical('Got sig {}, exiting...'.format(signum))
        cherrypy.engine.exit()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        cherrypy.engine.start()
        cherrypy.engine.block()
    finally:
        logging.info("API has shut down")
        cherrypy.engine.exit()


if __name__ == '__main__':
    main()
