def choose_action(enemy, arrows, hp):
    # enemy - словарь: distance, hp, damage, armor, is_aiming.
    # arrows - сколько стрел осталось.
    # hp - здоровье лучника.
    #
    # Порядок решений:
    # 1. Нет стрел -> "reload"
    # 2. Опасный враг целится, а здоровья мало -> "shield"
    # 3. Близкий или слабый враг без тяжелой брони -> "shoot"
    # 4. Иначе экономим стрелы -> "wait"
    if arrows <= 0:
        return "reload"

    threat = enemy["damage"] - enemy["distance"] * 2
    if enemy["is_aiming"] and threat >= 20:
        # TODO: щит нужен только если здоровье меньше 50.
        return "wait"

    return "wait"
