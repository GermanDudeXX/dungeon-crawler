import random

WALL = 0
FLOOR = 1


class Room:
    def __init__(self, x, y, w, h):
        self.x1, self.y1 = x, y
        self.x2, self.y2 = x + w, y + h

    def center(self):
        return (self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2

    def intersects(self, other, padding=1):
        return (
            self.x1 - padding < other.x2
            and self.x2 + padding > other.x1
            and self.y1 - padding < other.y2
            and self.y2 + padding > other.y1
        )


def generate_dungeon(width, height, max_rooms=15, room_min=4, room_max=9):
    grid = [[WALL for _ in range(width)] for _ in range(height)]
    rooms = []

    for _ in range(max_rooms):
        w = random.randint(room_min, room_max)
        h = random.randint(room_min, room_max)
        x = random.randint(1, width - w - 2)
        y = random.randint(1, height - h - 2)
        new_room = Room(x, y, w, h)

        if any(new_room.intersects(r) for r in rooms):
            continue

        _carve_room(grid, new_room)

        if rooms:
            prev_x, prev_y = rooms[-1].center()
            new_x, new_y = new_room.center()
            if random.random() < 0.5:
                _carve_h_tunnel(grid, prev_x, new_x, prev_y)
                _carve_v_tunnel(grid, prev_y, new_y, new_x)
            else:
                _carve_v_tunnel(grid, prev_y, new_y, prev_x)
                _carve_h_tunnel(grid, prev_x, new_x, new_y)

        rooms.append(new_room)

    return grid, rooms


def _carve_room(grid, room):
    for y in range(room.y1, room.y2):
        for x in range(room.x1, room.x2):
            grid[y][x] = FLOOR


def _carve_h_tunnel(grid, x1, x2, y):
    for x in range(min(x1, x2), max(x1, x2) + 1):
        grid[y][x] = FLOOR


def _carve_v_tunnel(grid, y1, y2, x):
    for y in range(min(y1, y2), max(y1, y2) + 1):
        grid[y][x] = FLOOR


def is_walkable(grid, x, y):
    if y < 0 or y >= len(grid) or x < 0 or x >= len(grid[0]):
        return False
    return grid[y][x] == FLOOR
