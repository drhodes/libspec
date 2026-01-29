from libspec import *
DATE = "2026-01-28"

class SingleFile(SystemRequirement):
    def req_id(self):  return "REQ-006"
    def title(self):   return "one-source-file"
    def actor(self):   return "LLM"
    def action(self):  return "generate API spec in a single source file"
    def benefit(self): return "simplifies example and makes it self contained"

class ProgrammingLanguage(SystemRequirement):
    def req_id(self):  return "REQ-007"
    def title(self):   return "specifies programming languages"
    def actor(self):   return "LLM"
    def action(self):  return "Uses the Python programming langauge"
    def benefit(self): return "tells the LLM which programming languages to use"

## --- FEATURES ---
class DisplyArg(Feature):
    def date(self): return DATE
    def description(self): return 'Display a command line arg on the terminal followed by a new line.'
    

class HelloCmdLine(CmdLine):
    
    def help(self):
        '''show this help dialog'''
        return "-h --help"
    def name(self):
        '''provide a name to greet'''
        return "-n --name"
    def repeat(self):
        '''repeat word N times.'''
        return "-r --repeat (N:int)"

    
## --- SPEC ASSEMBLY ---
class Spec:
    def __init__(self):
        self.components = [
            ProgrammingLanguage(),
            SingleFile(),
            HelloCmdLine(),
        ]

    def generate_full_spec(self):
        return ("\n" + (80 * '-') + "\n").join(c.render() for c in self.components)

if __name__ == "__main__":
    spec_doc = Spec().generate_full_spec()
    print(spec_doc)
