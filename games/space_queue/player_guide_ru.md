# Очередь кораблей

## Раздел

**Списки и цели**. Задача тренирует сортировку списка по вычисленной оценке.

## Цель игры

К станции прилетели корабли. Нужно построить очередь обслуживания: самый срочный корабль должен быть первым.

## Что видно в визуализации

На экране диспетчера показаны корабли, топливо, поломки, пассажиры и итоговая срочность. Активный корабль подсвечивается.

## Входные данные

`ships` - список словарей. У корабля есть:

- `id`
- `priority`
- `fuel`
- `broken`
- `passengers`
- `service_time`

## Как думать

Посчитайте срочность:

```python
urgency = priority * 10 + passengers * 2 + broken_bonus + (10 - fuel) - service_time
```

Если `broken == True`, `broken_bonus = 20`, иначе `0`.

Отсортируйте корабли по убыванию срочности. При равенстве используйте `id`, чтобы порядок был стабильным.

## Пример решения

```python
def schedule(ships):
    def urgency(ship):
        repair_bonus = 20 if ship["broken"] else 0
        return (
            ship["priority"] * 10
            + ship["passengers"] * 2
            + repair_bonus
            + (10 - ship["fuel"])
            - ship["service_time"]
        )

    ordered = sorted(ships, key=lambda ship: (-urgency(ship), ship["id"]))
    result = []
    for ship in ordered:
        result.append(ship["id"])
    return result
```

## Частые ошибки

- Сортировать по возрастанию вместо убывания.
- Вернуть весь словарь корабля вместо `id`.
- Забыть вычесть `service_time`.
