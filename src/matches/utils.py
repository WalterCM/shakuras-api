import math

class Vector2D:
    def __init__(self, x=0.0, y=0.0):
        self.x = float(x)
        self.y = float(y)

    def copy(self):
        return Vector2D(self.x, self.y)

    def __add__(self, other):
        return Vector2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vector2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        return Vector2D(self.x * scalar, self.y * scalar)

    def __truediv__(self, scalar):
        if scalar == 0:
            return Vector2D(0, 0)
        return Vector2D(self.x / scalar, self.y / scalar)

    def length_sq(self):
        return self.x**2 + self.y**2

    def length(self):
        return math.sqrt(self.length_sq())

    def dist_to(self, other):
        return (self - other).length()

    def dist_to_sq(self, other):
        return (self - other).length_sq()

    def normalize(self):
        l = self.length()
        if l > 0:
            return self / l
        return Vector2D(0, 0)

    def to_tuple(self):
        return (self.x, self.y)

    def __repr__(self):
        return f"Vec({round(self.x, 2)}, {round(self.y, 2)})"
