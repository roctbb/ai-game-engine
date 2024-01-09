from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import backref

db = SQLAlchemy()

team_session = db.Table('team_session',
                        db.Column('team_id', db.Integer, db.ForeignKey('team.id', ondelete="CASCADE")),
                        db.Column('session_id', db.Integer, db.ForeignKey('session.id', ondelete="CASCADE"))
                        )


class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    code = db.Column(db.String(128), nullable=False)
    team_size = db.Column(db.Integer, nullable=False, default=1)
    team_number = db.Column(db.Integer, nullable=False, default=2)
    team_roles = db.Column(db.JSON, nullable=True)

    teams = db.relationship('Team', backref=backref('game', uselist=False), lazy=True)
    lobby = db.relationship('Lobby', backref=backref('game', uselist=False), lazy=True)
    sessions = db.relationship('Session', backref=backref('game', uselist=False), lazy=True)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(128), nullable=False)
    password = db.Column(db.String(1024), nullable=False)
    teams = db.relationship('Team', backref=backref('user', uselist=False), lazy=True)
    created_sessions = db.relationship('Session', backref=backref('creator', uselist=False), lazy=True)


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"))
    game_id = db.Column(db.Integer, db.ForeignKey('game.id', ondelete="CASCADE"))
    players = db.relationship('Player', backref=backref('game', uselist=False), lazy=True)


class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=True)
    script = db.Column(db.Text, nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id', ondelete="CASCADE"))


class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id', ondelete="CASCADE"))
    state = db.Column(db.String(128), nullable=True)
    stats = db.Column(db.JSON, nullable=True)
    description = db.Column(db.JSON, nullable=True)
    replay = db.Column(db.JSON, nullable=True)
    engine_pid = db.Column(db.Integer, nullable=True)
    created_on = db.Column(db.DateTime, server_default=db.func.now())
    updated_on = db.Column(db.DateTime, server_default=db.func.now(), server_onupdate=db.func.now())
    winner_id = db.Column('team_id', db.Integer, db.ForeignKey('team.id'))
    teams = db.relationship('Team', secondary=team_session, backref='sessions')
    created_by = db.Column('created_by', db.Integer, db.ForeignKey('user.id'))


class Lobby(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"))
    game_id = db.Column(db.Integer, db.ForeignKey('game.id', ondelete="CASCADE"))
    description = db.Column(db.JSON, nullable=True)
    