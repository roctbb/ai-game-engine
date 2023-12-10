class PlayersRepository:
    def __init__(self, connection):
        self.connection = connection

    def all(self):
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM players WHERE state = 'ready'")

        return cursor.fetchall()

    def get(self, id):
        cursor = self.connection.cursor()
        cursor.execute('SELECT * FROM players WHERE id = %s', (id,))

        return cursor.fetchone()
