import os
import shutil

from models import db, Game
from server import app

title = input("Enter short game title (a-z, _):")
prepared_title = title.strip().replace(' ', '_')

min_teams = int(input('Минимальное число команд: '))
max_teams = int(input('Максимальное число команд: '))
min_team_players = int(input('Минимальное число игроков в команде: '))
max_team_players = int(input('Максимальное число игроков в команде: '))

with app.app_context():
    shutil.copytree('./games/template', './games/{}'.format(prepared_title))

    # replace 'GAME_TITLE' in files.
    for dirpath, dirnames, filenames in os.walk('./games/{}'.format(prepared_title)):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            with open(filepath, 'r') as file:
                filedata = file.read()
            filedata = filedata.replace('GAME_TITLE', prepared_title)
            with open(filepath, 'w') as file:
                file.write(filedata)

    game = Game(name=prepared_title, code=prepared_title, min_teams=min_teams, max_teams=max_teams,
                min_team_players=min_team_players, max_team_players=max_team_players)
    db.session.add(game)
    db.session.commit()

print("Game created successfully!")
