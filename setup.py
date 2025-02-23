from os import system, path

# Init database
system('flask db init')
system('flask db upgrade')

# Add tic tac toe to database
from models import Game, db
from server import app

with app.app_context():
    if not path.exists('config.py'):
        with open('config.py', 'w') as f:
            f.write(open('./config.py.example').read())

    if not Game.query.filter_by(code='tic_tac_toe').count():
        game = Game(name='Tic Tac Toe', code='tic_tac_toe', min_teams=2, max_teams=2, min_team_players=1,
                    max_team_players=1)
        db.session.add(game)
    if not Game.query.filter_by(code='tanks').count():
        game = Game(name='Tanks', code='tanks', min_teams=1, max_teams=12, min_team_players=1, max_team_players=1)
        db.session.add(game)
    db.session.commit()

print('Run "python server.py" to start the engine!')
