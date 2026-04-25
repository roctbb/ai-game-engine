def paint(pixels, palette):
    # pixels[x][y] - числовой код пикселя.
    # palette[код] - название цвета.
    result = []

    for x in range(len(pixels)):
        column = []
        for y in range(len(pixels[x])):
            # TODO: возьмите числовой код pixels[x][y].
            # TODO: найдите цвет в palette и добавьте его в column.
            color_number = pixels[x][y]
            color = palette[color_number]
            column.append(color)
        result.append(column)

    return result
