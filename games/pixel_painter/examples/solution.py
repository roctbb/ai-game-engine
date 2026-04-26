def paint(pixels, palette):
    result = []
    for x in range(len(pixels)):
        column = []
        for y in range(len(pixels[x])):
            column.append(palette.get(pixels[x][y], "transparent"))
        result.append(column)
    return result
