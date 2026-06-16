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

    @property
    def length(self):
        import math
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)
    def normalized(self):
        l = self.length
        if l == 0: return Vector((0,0,0))
        return Vector((self.x/l, self.y/l, self.z/l))


    def copy(self):
        return Vector((self.x, self.y, self.z))


    def normalize(self):
        l = self.length
        if l != 0:
            self.x /= l
            self.y /= l
            self.z /= l

