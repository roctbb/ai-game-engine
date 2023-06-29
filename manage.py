from flask import Flask
from models import db
from flask_migrate import Migrate
from flask_cors import CORS

from config import *

app = Flask(__name__)
db_string = "postgresql://{}:{}@{}:{}/{}".format(DB_LOGIN, DB_PASSWORD, DB_HOST, DB_PORT, DB_DATABASE)
app.config['SQLALCHEMY_DATABASE_URI'] = db_string
app.config['SECRET_KEY'] = 'secret!'

db.init_app(app)

migrate = Migrate(app, db)
CORS(app)
