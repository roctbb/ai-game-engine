from os import system

# Init database
system('flask db init')
system('flask db upgrade')

# Add tic tac toe to database
from server import app, Game, db

with app.app_context():
    if not Game.query.filter_by(code='tic_tac_toe').count():
        game = Game(name='Tic Tac Toe', code='tic_tac_toe', min_teams=2, max_teams=2, min_team_players=1,
                    max_team_players=1)
        db.session.add(game)
    if not Game.query.filter_by(code='tanks').count():
        game = Game(name='Tanks', code='tanks', min_teams=1, max_teams=12, min_team_players=1, max_team_players=1)
        db.session.add(game)
    db.session.commit()

print('Run "python server.py" to start the engine!')
