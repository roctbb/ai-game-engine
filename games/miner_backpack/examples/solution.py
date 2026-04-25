def solve(ores, capacity):
    total = 0
    count = 0
    for ore in ores:
        if total + ore > capacity:
            break
        total += ore
        count += 1
    return count
