import os
import cherrypy
import logging
from photoapp.library import PhotoLibrary
from photoapp.types import Photo, PhotoSet
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import func


class PhotosWeb(object):
    def __init__(self, library):
        self.library = library
        self.tpl = Environment(loader=FileSystemLoader('templates'),
                               autoescape=select_autoescape(['html', 'xml']))
        self.tpl.globals.update(mime2ext=self.mime2ext)
        self.thumb = ThumbnailView(self)
        self.photo = PhotoView(self)
        self.download = DownloadView(self)

    def session(self):
        return self.library.session()

    @staticmethod
    def mime2ext(mime):
        return {"image/png": "png",
                "image/jpeg": "jpg",
                "image/gif": "gif",
                "application/octet-stream-xmp": "xmp",
                "image/x-canon-cr2": "cr2",
                "video/mp4": "mp4"}[mime]

    @cherrypy.expose
    def index(self):
        raise cherrypy.HTTPRedirect('feed', 302)

    @cherrypy.expose
    def feed(self, page=0, pgsize=25):
        s = self.session()
        page, pgsize = int(page), int(pgsize)
        images = s.query(PhotoSet).order_by(PhotoSet.date.desc()).offset(pgsize * page).limit(pgsize).all()
        yield self.tpl.get_template("feed.html").render(images=[i for i in images], page=page)

    @cherrypy.expose
    def monthly(self):
        s = self.session()
        images = s.query(func.count(PhotoSet.uuid),
                         func.strftime('%Y', PhotoSet.date).label('year'),
                         func.strftime('%m', PhotoSet.date).label('month')). \
            group_by('year', 'month').order_by('year', 'month').all()

        yield self.tpl.get_template("monthly.html").render(images=images)


@cherrypy.popargs('item_type', 'thumb_size', 'uuid')
class ThumbnailView(object):
    def __init__(self, master):
        self.master = master
        self._cp_config = {"tools.trailing_slash.on": False}

    @cherrypy.expose
    def index(self, item_type, thumb_size, uuid):
        uuid = uuid.split(".")[0]
        s = self.master.session()

        query = s.query(Photo).filter(Photo.set.has(uuid=uuid)) if item_type == "set" \
            else s.query(Photo).filter(Photo.uuid == uuid) if item_type == "one" \
            else None

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
            raise Exception("404")  # TODO it right
        # TODO some lock around calls to this based on uuid
        thumb_path = self.master.library.make_thumb(thumb_from, thumb_size)
        if thumb_path:
            return cherrypy.lib.static.serve_file(thumb_path, 'image/jpeg')
        else:
            return "No thumbnail available"  # TODO generic svg icon


@cherrypy.popargs('item_type', 'uuid')
class DownloadView(object):
    def __init__(self, master):
        self.master = master
        self._cp_config = {"tools.trailing_slash.on": False}

    @cherrypy.expose
    def index(self, item_type, uuid, preview=False):
        uuid = uuid.split(".")[0]
        s = self.master.session()

        query = None if item_type == "set" \
            else s.query(Photo).filter(Photo.uuid == uuid) if item_type == "one" \
            else None  # TODO set download query

        item = query.first()
        extra = {}
        if not preview:
            extra.update(disposition="attachement", name=os.path.basename(item.path))
        return cherrypy.lib.static.serve_file(os.path.abspath(os.path.join(self.master.library.path, item.path)),
                                              content_type=item.format, **extra)


@cherrypy.popargs('uuid')
class PhotoView(object):
    def __init__(self, master):
        self.master = master
        self._cp_config = {"tools.trailing_slash.on": False}

    @cherrypy.expose
    def index(self, uuid):
        uuid = uuid.split(".")[0]
        s = self.master.session()
        photo = s.query(PhotoSet).filter(PhotoSet.uuid == uuid).first()

        yield self.master.tpl.get_template("photo.html").render(image=photo)

        # yield "viewing {}".format(uuid)


def main():
    import argparse
    import signal

    parser = argparse.ArgumentParser(description="Photod photo server")

    parser.add_argument('-p', '--port', default=8080, type=int, help="tcp port to listen on")
    parser.add_argument('-l', '--library', default="./library", help="library path")
    parser.add_argument('-s', '--database-path', default="./photos.db", help="path to persistent sqlite database")
    parser.add_argument('--debug', action="store_true", help="enable development options")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.debug else logging.WARNING,
                        format="%(asctime)-15s %(levelname)-8s %(filename)s:%(lineno)d %(message)s")

    library = PhotoLibrary(args.database_path, args.library)

    web = PhotosWeb(library)
    web_config = {}

    # TODO make auth work again
    if True or args.disable_auth:
        logging.warning("starting up with auth disabled")
    else:
        def validate_password(realm, username, password):
            print("I JUST VALIDATED {}:{} ({})".format(username, password, realm))
            return True

        web_config.update({'tools.auth_basic.on': True,
                           'tools.auth_basic.realm': 'pysonic',
                           'tools.auth_basic.checkpassword': validate_password})

    cherrypy.tree.mount(web, '/', {'/': web_config,
                                   '/static': {"tools.staticdir.on": True,
                                               "tools.staticdir.dir": os.path.abspath("./styles/dist")}})

    cherrypy.config.update({
        'sessionFilter.on': True,
        'tools.sessions.on': True,
        'tools.sessions.locking': 'explicit',
        'tools.sessions.timeout': 525600,
        'tools.gzip.on': True,
        'request.show_tracebacks': True,
        'server.socket_port': args.port,
        'server.thread_pool': 25,
        'server.socket_host': '0.0.0.0',
        'server.show_tracebacks': True,
        'server.socket_timeout': 5,
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