# Инвентарь героя

## Раздел

**Списки и цели**. Нужно проверить, есть ли нужный предмет в списке, и выбрать самый важный.

## Цель игры

Герой попадает в разные ситуации: мало здоровья, яд, закрытая дверь, темнота или голод. Нужно выбрать предмет из инвентаря.

## Что видно в визуализации

Визуал показывает героя, дверь, темноту и сетку предметов. Предмет, который подходит по текущей ситуации, подсвечивается.

## Входные данные

- `inventory` - список строк, например `["torch", "apple", "small_key"]`.
- `situation` - словарь с признаками:
  - `hp`
  - `poisoned`
  - `door`
  - `dark`
  - `hungry`

## Как думать

Проверяйте условия по приоритету. Низкое здоровье важнее яда, яд важнее двери, дверь важнее темноты, темнота важнее голода.

## Пример решения

```python
def choose_item(inventory, situation):
    if situation["hp"] < 40 and "healing_potion" in inventory:
        return "healing_potion"
    elif situation["poisoned"] and "antidote" in inventory:
        return "antidote"
    elif situation["door"] and "small_key" in inventory:
        return "small_key"
    elif situation["dark"] and "torch" in inventory:
        return "torch"
    elif situation["hungry"] and "apple" in inventory:
        return "apple"
    elif "rope" in inventory:
        return "rope"
    return "apple"
```

## Частые ошибки

- Выбрать ключ при низком здоровье.
- Не проверить, есть ли предмет в `inventory`.
- Перепутать порядок приоритетов.
