import ge_sdk as sdk


def game():
    engine = sdk.GameEngineClient()

    engine.start()

    # engine.teams - команды

    # team = engine.teams[0]
    # team.id - id команды 0
    # team.name - имя команды 0
    # team.players - игроки команды 0

    # player = team.players[0]
    # player.id - id игрока
    # player.name - имя игрока
    # player.script - скрипт игрока

    # Запуск скрипта игрока и получение значения:
    # result = sdk.timeout_run(0.4, player.script, "function_name", (arg1, arg2, arg3...))
    # 0.4 - таймаут выполнения, при превышении вернет None
    # "function_name" - имя функции из скрипта игрока, которую хотите запустить
    # (arg1, arg2, arg3...) - список аргументов, которые нужно передать в функцию игрока


    while True:
        frame = {}

        # TODO: запросить ход у каждого игрока и сформировать кадр

        engine.send_frame(frame)

        # если кто-то одержал победу - прерываем игру
        # if winner:
        #     break


    # TODO: указать, какая команда победила
    # engine.set_winner(engine.teams[0])

    engine.end()


if __name__ == "__main__":
    game()
