import random


def generate_maze(width, height):
    # Создаем начальную матрицу, заполняя все стены
    maze = [['#' for _ in range(width)] for _ in range(height)]

    # Функция для проверки выхода за границы лабиринта
    def in_bounds(x, y):
        return 0 <= x < width and 0 <= y < height

    # Функция для создания проходов в лабиринте
    def dfs(x, y):
        # Устанавливаем текущую клетку как пустую
        maze[y][x] = '.'

        # Перемешиваем направления для случайности
        directions = [(0, 2), (2, 0), (0, -2), (-2, 0)]
        random.shuffle(directions)

        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            mx, my = x + dx // 2, y + dy // 2

            # Если целевая клетка и промежуточная клетка внутри границ и еще не посещены
            if in_bounds(nx, ny) and maze[ny][nx] == '#':
                # Делаем проход между текущей и целевой клеткой
                maze[my][mx] = '.'
                # Рекурсивно продолжаем генерацию лабиринта
                dfs(nx, ny)

    # Начинаем генерацию лабиринта с верхнего левого угла
    dfs(1, 1)

    # Гарантируем, что стартовая и конечная точки лабиринта доступны
    maze[1][1] = '.'
    maze[height - 2][width - 2] = '.'

    return maze


# Вывод лабиринта
def print_maze(maze):
    for row in maze:
        print(''.join(row))


if __name__ == "__main__":
    width, height = map(int, input("Введите ширину и высоту лабиринта (например, 21 21): ").split())

    # Ширина и высота должны быть нечетными
    if width % 2 == 0:
        width += 1
    if height % 2 == 0:
        height += 1

    maze = generate_maze(width, height)
    print_maze(maze)