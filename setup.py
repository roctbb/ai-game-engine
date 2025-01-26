from os import system

# Install requirements
system('pip install -r requirements.txt')

# Init database
system('flask db init')
system('flask db migrate')
system('flask db upgrade')

# Add tic tac toe to database
from server import app, Game, db

with app.app_context():
    game = Game(name='Tic Tac Toe', code='tic_tac_toe')
    db.session.add(game)
    db.session.commit()

print('Run "python server.py" to start the engine!')