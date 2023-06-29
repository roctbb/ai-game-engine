from models import User, db
from .exceptions import *
import hashlib


def hash(password):
    return hashlib.md5(password.encode())


def create_user(login, password):
    if not login or not password:
        raise InsufficientData

    if User.query.filter_by(login=login).first():
        raise AlreadyExists

    user = User(login=login, password=hash(password))

    db.session.add(user)
    db.session.commit()

    return user


def get_user(login):
    return User.query.filter_by(login=login).first()


def delete_user(user):
    db.session.delete(user)
    db.session.commit()
