from os import system

# Install requirements
system('pip install -r requirements.txt')

# Init database
system('flask db init')
system('flask db migrate')
system('flask db upgrade')

print('Run "python server.py" to start the engine!')