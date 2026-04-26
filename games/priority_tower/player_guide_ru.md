# Башня приоритета

## Раздел

**Списки и цели**. Нужно перебрать список врагов и выбрать лучший объект по формуле.

## Цель игры

К базе идут враги. У каждого есть опасность, скорость, расстояние и здоровье. Башня должна выбрать цель для выстрела.

## Что видно в визуализации

На поле показана башня, враги и их счет опасности. Выбранный враг подсвечивается, а линия выстрела показывает решение.

## Входные данные

`enemies` - список словарей. У каждого врага есть:

- `id`
- `danger`
- `speed`
- `distance`
- `hp`

## Как думать

Для каждого врага посчитайте:

```python
score = danger * 3 + speed * 2 - distance + hp // 10
```

Выберите врага с максимальным `score`. Если счет равен, выберите ближайшего. Если и расстояние равно, выберите врага с большим `hp`.

## Пример решения

```python
def choose_target(enemies):
    best = enemies[0]
    best_score = best["danger"] * 3 + best["speed"] * 2 - best["distance"] + best["hp"] // 10

    for enemy in enemies:
        score = enemy["danger"] * 3 + enemy["speed"] * 2 - enemy["distance"] + enemy["hp"] // 10
        if score > best_score:
            best = enemy
            best_score = score
        elif score == best_score and enemy["distance"] < best["distance"]:
            best = enemy
            best_score = score
        elif score == best_score and enemy["distance"] == best["distance"] and enemy["hp"] > best["hp"]:
            best = enemy
            best_score = score

    return best["id"]
```

## Частые ошибки

- Выбирать по одному признаку, например только по `danger`.
- Забыть обновить `best_score`.
- Не обработать равенство счета.
