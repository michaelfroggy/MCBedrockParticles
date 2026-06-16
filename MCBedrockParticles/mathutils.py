class Vector:
    def __init__(self, t):
        self.x = t[0]
        self.y = t[1]
        self.z = t[2]
    def __add__(self, other):
        return Vector((self.x + other.x, self.y + other.y, self.z + other.z))
    def __mul__(self, scalar):
        return Vector((self.x * scalar, self.y * scalar, self.z * scalar))
    def __str__(self):
        return f"({self.x:.2f}, {self.y:.2f}, {self.z:.2f})"
