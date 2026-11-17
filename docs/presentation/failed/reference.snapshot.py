def energy(values: list[float]) -> float:
    total = 0.0
    for value in values:
        total += value * value
    return total
