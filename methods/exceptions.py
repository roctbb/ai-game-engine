class ExplainableException(Exception):
    pass

class InsufficientData(ExplainableException):
    text = "Недостаточно данных"


class AlreadyExists(ExplainableException):
    text = "Уже существует"


class IncorrectNumberOfTeams(ExplainableException):
    text = "Неправильное число команд"


class IncorrectTeam(ExplainableException):
    text = "Неподходящая команда"


class LobbyFull(ExplainableException):
    text = "Лобби заполнено"


class IncorrectPlayer(ExplainableException):
    text = "Неподходящий игрок"


class NotFound(ExplainableException):
    text = "Не найдено"


class IncorrectPassword(ExplainableException):
    text = "Неверный пароль"
