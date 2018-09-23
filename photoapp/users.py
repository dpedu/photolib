import argparse
from photoapp.library import PhotoLibrary
from photoapp.types import User
from photoapp.common import pwhash


def create_user(library, username, password):
    s = library.session()
    s.add(User(name=username, password=pwhash(password)))
    s.commit()


def list_users(library):
    s = library.session()
    print("id\tname")
    for user in s.query(User).order_by(User.name).all():
        print("{}\t{}".format(user.id, user.name))


def delete_user(library, username):
    s = library.session()
    u = s.query(User).filter(User.name == username).first()
    s.delete(u)
    s.commit()
    print("Deleted user {}".format(u.id))


def main():
    parser = argparse.ArgumentParser(description="User manipulation tool")
    p_mode = parser.add_subparsers(dest='action', help='action to take')

    p_create = p_mode.add_parser('create', help='create user')
    p_create.add_argument("-u", "--username", help="username", required=True)
    p_create.add_argument("-p", "--password", help="password", required=True)

    p_list = p_mode.add_parser('list', help='list users')

    p_delete = p_mode.add_parser('delete', help='delete users')
    p_delete.add_argument("-u", "--username", help="username", required=True)

    args = parser.parse_args()

    library = PhotoLibrary("photos.db", "./library/", "./cache/")

    if args.action == "create":
        create_user(library, args.username, args.password)
    elif args.action == "list":
        list_users(library)
    elif args.action == "delete":
        delete_user(library, args.username)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
