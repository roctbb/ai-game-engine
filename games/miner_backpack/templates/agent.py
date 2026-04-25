def solve(ores, capacity):
    # ores - веса кусков руды по порядку.
    # capacity - максимальный вес рюкзака.
    total = 0
    count = 0

    for ore in ores:
        # Берем только пока следующий кусок помещается.
        if total + ore > capacity:
            break
        total += ore
        count += 1

    return count
