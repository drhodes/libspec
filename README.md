# libspec

`libspec` is a tool for **Specification-Driven Development** in Python.

Instead of just writing code, you first define *what your code should do* in a clear, structured `spec.py` file. This specification becomes the source of truth for your project's requirements, features, and constraints. You can then use this spec to guide your development and automatically test that your code works as specified.

### What does it look like?

`libspec` helps you formalize your project's goals. Imagine you want to build a simple temperature conversion tool.

First, you'd write a specification file. This file defines the data structures and requirements. It's plain Python:

**`examples/temperature-conversion/spec.py`**
```python
from libspec import DataSchema, Requirement

# 1. Define the data we're working with
class TemperatureState(DataSchema):
    """Represents a temperature value and unit"""
    value: float
    unit : str  # "C" or "F"

# 2. Define a requirement for the system
class ConvertCtoF(Requirement):
    def req_id(self): return "REQ-001"
    def title(self): return "Convert Celsius to Fahrenheit"
    def actor(self): return "user"
    def action(self): return "input a temperature in Celsius"
    def benefit(self): return "get the equivalent temperature in Fahrenheit"
```

Then, you write the actual application code. Notice the comments `REQ-001` and `CONST-001`? They link back to the requirements defined in your spec. `libspec` can use these links to trace which parts of your code satisfy which requirements.

**`examples/temperature-conversion/main.py`**
```python
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

# Pytest tests are included in the same file to verify behavior
def test_c_to_f():
    temp = TemperatureState(0, 'C')
    converted = convert_temperature(temp)
    assert converted.unit == 'F'
    assert abs(converted.value - 32) < 1e-6
```

### How do you run an example?

You can run the tests for the `temperature-conversion` example to see it in action. This project uses `uv` for managing dependencies and running commands.

1.  Navigate to the example's directory:
    ```sh
    cd examples/temperature-conversion
    ```

2.  Run the tests using `uv` and `pytest`:
    ```sh
    uv run pytest
    ```

    `uv` will automatically create a virtual environment, install `pytest`, and then run the tests located in `main.py`. You should see the tests pass, confirming that the code meets the specification's requirements.

---

For more examples, see the [examples README](examples/README.md).
