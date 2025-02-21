from flask import Blueprint
from flask import render_template, request, redirect

from methods import *

auth_blueprint = Blueprint('auth', __name__)


@auth_blueprint.route('/login', methods=['get'])
def login_page():
    return render_template('auth/auth.html')


@auth_blueprint.route('/login', methods=['post'])
def make_login():
    login = request.form.get('login')
    password = request.form.get('password')

    try:
        user = find_user(login, password)
    except InsufficientData:
        return render_template('auth/auth.html', error='Введите логин и пароль', login=login)
    except NotFound:
        return render_template('auth/auth.html', error='Пользователь не найден', login=login)
    except IncorrectPassword:
        return render_template('auth/auth.html', error='Неправильный пароль', login=login)

    authorize(user)

    return redirect('/')


@auth_blueprint.route('/register', methods=['get'])
def register_page():
    return render_template('auth/auth.html', register=True)


@auth_blueprint.route('/register', methods=['post'])
def register():
    login = request.form.get('login')
    password = request.form.get('password')

    try:
        user = create_user(login, password)
    except InsufficientData:
        return render_template('auth/auth.html', error='Введите логин и пароль', login=login, register=True)
    except AlreadyExists:
        return render_template('auth/auth.html', error='Логин уже занят', login=login, register=True)

    authorize(user)

    return redirect('/')


@auth_blueprint.route('/logout', methods=['get'])
def logout():
    deauthorize()

    return redirect('/login')
