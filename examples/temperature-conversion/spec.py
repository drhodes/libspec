from libspec import DataSchema, Requirement, Feature, Constraint, SystemRequirement

DATE = "2026-01-28"

## --- DATA SCHEMA ---
class TemperatureState(DataSchema):
    """Represents a temperature value and unit"""
    value: float
    unit : str  # "C" or "F"
   

## --- REQUIREMENTS ---
class ConvertCtoF(Requirement):
    def req_id(self): return "REQ-001"
    def title(self): return "Convert Celsius to Fahrenheit"
    def actor(self): return "user"
    def action(self): return "input a temperature in Celsius"
    def benefit(self): return "get the equivalent temperature in Fahrenheit"

class ConvertFtoC(Requirement):
    def req_id(self): return "REQ-002"
    def title(self): return "Convert Fahrenheit to Celsius"
    def actor(self): return "user"
    def action(self): return "input a temperature in Fahrenheit"
    def benefit(self): return "get the equivalent temperature in Celsius"

class Test1(SystemRequirement):
    def req_id(self): return "REQ-003"
    def title(self): return "test1"
    def actor(self): return "system"
    def action(self): return "build a comprehensive test suite in pytest"
    def benefit(self): return "ensure code behaves as expected"


class SingleFile(SystemRequirement):
    def req_id(self):  return "REQ-004"
    def title(self):   return "one-source-file"
    def actor(self):   return "LLM"
    def action(self):  return "The LLM should generate a program in a single source file."
    def benefit(self): return "makes it easier to manage copy pasting"
   
    
## --- FEATURES ---
class ConvertTemperature(Feature):
    def feature_name(self): return "convert-temperature"
    def date(self): return DATE
    def description(self): return "Converts temperature values between Celsius and Fahrenheit."


## --- CONSTRAINTS ---
class ValidUnits(Constraint):
    def constraint_id(self): return "CONST-001"
    def description(self): return "Temperature units must be 'C' or 'F'."
    def enforcement_logic(self):
        return "Raise an error if unit not in ['C','F']"


## --- SPEC ASSEMBLY ---
class TempConverterSpec:
    def __init__(self):
        self.components = [
            TemperatureState(),
            ConvertCtoF(),
            ConvertFtoC(),
            ConvertTemperature(),
            ValidUnits(),
            #
            SingleFile(),
            Test1(), 
        ]

    def generate_full_spec(self):
        return "\n\n".join(c.render() for c in self.components)


## --- USAGE ---
if __name__ == "__main__":
    spec_doc = TempConverterSpec().generate_full_spec()
    print(spec_doc)



    
