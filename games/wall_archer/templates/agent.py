def choose_action(enemy, arrows, hp):
    # enemy - словарь: enemy["distance"], enemy["hp"], enemy["is_aiming"].
    # arrows - сколько стрел осталось.
    # hp - здоровье лучника.
    #
    # Порядок решений:
    # 1. Нет стрел -> "reload"
    # 2. Враг близко (distance <= 3) -> "shoot"
    # 3. Враг целится и hp < 50 -> "shield"
    # 4. Иначе -> "wait"
    if arrows <= 0:
        return "reload"
    return "wait"
