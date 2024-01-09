import os
import shutil
from server import app, Game, db

title = input("Enter short game title (a-z, _):")
prepared_title = title.strip().replace(' ', '_')

team_number = int(input("How many teams would you like:"))
team_size = int(input("Enter team size:"))

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

    game = Game(name=prepared_title, code=prepared_title, team_number=team_number, team_size=team_size)
    db.session.add(game)
    db.session.commit()

print("Game created successfully!")
