# temperature_tool.py
from dataclasses import dataclass

@dataclass(frozen=True)
class TemperatureState:
    """Represents a temperature value and unit"""
    value: float
    unit: str  # Must be 'C' or 'F'

    def __post_init__(self):
        if self.unit not in ('C', 'F'):
            raise ValueError("Unit must be 'C' or 'F'")  # CONST-001


def convert_temperature(temp: TemperatureState) -> TemperatureState:
    """
    Converts a temperature between Celsius and Fahrenheit.
    REQ-001: C -> F
    REQ-002: F -> C
    """
    if temp.unit == 'C':
        return TemperatureState(value=temp.value * 9 / 5 + 32, unit='F')
    elif temp.unit == 'F':
        return TemperatureState(value=(temp.value - 32) * 5 / 9, unit='C')
    else:
        # Defensive, though TemperatureState already enforces CONST-001
        raise ValueError("Unit must be 'C' or 'F'")


# -------------------------
# Pytest Suite (REQ-003)
# -------------------------
def _approx_eq(a, b, tol=1e-6):
    return abs(a - b) < tol


def test_c_to_f():
    temp = TemperatureState(0, 'C')
    converted = convert_temperature(temp)
    assert converted.unit == 'F'
    assert _approx_eq(converted.value, 32)


def test_f_to_c():
    temp = TemperatureState(212, 'F')
    converted = convert_temperature(temp)
    assert converted.unit == 'C'
    assert _approx_eq(converted.value, 100)


def test_negative_and_decimal():
    # Check negative Celsius
    temp = TemperatureState(-40, 'C')
    converted = convert_temperature(temp)
    assert converted.unit == 'F'
    assert _approx_eq(converted.value, -40)

    # Check decimal Fahrenheit
    temp = TemperatureState(98.6, 'F')
    converted = convert_temperature(temp)
    assert converted.unit == 'C'
    assert _approx_eq(converted.value, 37)


def test_invalid_unit():
    import pytest
    with pytest.raises(ValueError):
        TemperatureState(10, 'K')  # CONST-001 enforcement


if __name__ == "__main__":
    # Quick manual check
    for t in [TemperatureState(0, 'C'), TemperatureState(100, 'C'),
              TemperatureState(32, 'F'), TemperatureState(212, 'F')]:
        converted = convert_temperature(t)
        print(f"{t.value}{t.unit} -> {converted.value}{converted.unit}")

