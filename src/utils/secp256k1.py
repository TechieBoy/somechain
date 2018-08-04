from typing import Tuple

"""
TODO:
    add docstrings
"""
Point = Tuple[int, int]

# https://en.bitcoin.it/wiki/Secp256k1
P: int = (2 ** 256) - (2 ** 32) - (2 ** 9) - (2 ** 8) - (2 ** 7) - (2 ** 6) - (2 ** 4) - 1
G: Point = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
            0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)
B58_char = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'


def point_add(p: Point, q: Point) -> Point:
    px, py = p
    qx, qy = q

    if p == q:
        lmbda = pow(2 * py % P, P - 2, P) * (3 * px * px) % P
    else:
        lmbda = pow(qx - px, P - 2, P) * (qy - py) % P

    rx = (lmbda ** 2 - px - qx) % P
    ry = (lmbda * px - lmbda * rx - py) % P

    return rx, ry


def point_mul(d: int) -> Point:
    p = G
    n = p
    q = None

    for i in range(256):
        if d & (1 << i):
            if q is None:
                q = n
            else:
                q = point_add(q, n)

        n = point_add(n, n)

    return q


def b58_encode(d: bytes) -> str:
    out = ""
    p = 0
    x = 0

    while d[0] == 0:
        out += "1"
        d = d[1:]

    for i, v in enumerate(d[::-1]):
        x += v * (256 ** i)

    while x > 58 ** (p + 1):
        p += 1

    while p >= 0:
        a, x = divmod(x, 58 ** p)
        out += B58_char[a]
        p -= 1

    return out
