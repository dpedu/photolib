import hashlib


def pwhash(password):
    h = hashlib.sha256()
    h.update(password.encode("UTF-8"))
    return h.hexdigest()
