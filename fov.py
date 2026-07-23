import math


def _line(x0, y0, x1, y1):
    points = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy
    return points


def compute_fov(grid, origin_x, origin_y, radius, rays=180):
    visible = {(origin_x, origin_y)}
    height = len(grid)
    width = len(grid[0])

    for i in range(rays):
        angle = (2 * math.pi) * (i / rays)
        target_x = origin_x + radius * math.cos(angle)
        target_y = origin_y + radius * math.sin(angle)

        for x, y in _line(origin_x, origin_y, round(target_x), round(target_y)):
            if not (0 <= x < width and 0 <= y < height):
                break
            if (x - origin_x) ** 2 + (y - origin_y) ** 2 > radius * radius:
                break
            visible.add((x, y))
            if grid[y][x] == 0:
                break

    return visible
