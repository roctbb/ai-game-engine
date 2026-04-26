def decode(runes):
    # runes - строка рун. Нужно вернуть список команд.
    #
    # Таблица:
    # "ᚠ" -> "forward"
    # "ᚱ" -> "turn_right"
    # "ᛚ" -> "turn_left"
    # "ᚲ" -> "collect"
    # "ᚨ" -> "attack"
    # "᛫" -> "wait"
    mapping = {
        "ᚠ": "forward",
        # Допишите остальные руны по таблице выше.
    }
    commands = []
    for rune in runes:
        # get не падает, но для полного решения нужны все руны.
        commands.append(mapping.get(rune, "forward"))
    return commands
