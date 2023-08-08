pip install -r requirements.txt
flask db init
flask db migrate
flask db upgrade
echo Database initialized!