import hashlib

from flask import session

from models import User, db
from .exceptions import *


def hash(password):
    return hashlib.md5(password.encode()).hexdigest()


def create_user(login: str, password: str) -> User:
    if not login or not password:
        raise InsufficientData

    if User.query.filter_by(login=login).first():
        raise AlreadyExists

    user = User(login=login, password=hash(password))

    db.session.add(user)
    db.session.commit()

    return user


def find_user(login: str, password: str) -> User:
    if not login or not password:
        raise InsufficientData

    user = User.query.filter_by(login=login).first()
    if not user:
        raise NotFound

    if user.password != hash(password):
        raise IncorrectPassword

    return user


def authorize(user: User):
    session['login'] = user.login
    session['id'] = user.id


def deauthorize():
    session.clear()


def get_user(login: str) -> User:
    return User.query.filter_by(login=login).first()


def get_user_by_id(user_id: int) -> User:
    return User.query.filter_by(id=user_id).first()


def delete_user(user):
    db.session.delete(user)
    db.session.commit()
