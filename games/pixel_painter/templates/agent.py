def paint(pixels, palette):
    # pixels[x][y] - числовой код пикселя.
    # palette[код] - название цвета.
    # Если кода нет в palette, нужен цвет "transparent".
    result = []

    for x in range(len(pixels)):
        column = []
        for y in range(len(pixels[x])):
            code = pixels[x][y]
            # TODO: используйте palette.get(code, "transparent").
            column.append(palette[0])
        result.append(column)

    return result
