import jedi
import os

def test_jedi_hover():
    spec_py = os.path.abspath("libspec/spec.py")
    with open(spec_py, "r") as f:
        code = f.read()
    
    # Let's try to hover over 'Spec' or 'Ctx'
    # Find line for 'class Ctx'
    lines = code.splitlines()
    ctx_line = -1
    for i, line in enumerate(lines):
        if "class Ctx" in line:
            ctx_line = i + 1
            break
            
    print(f"Testing hover at line {ctx_line}, column 6 (word 'Ctx')...")
    script = jedi.Script(code, path=spec_py)
    definitions = script.goto(ctx_line, 6, follow_imports=True)
    
    if not definitions:
        print("No definitions found.")
        return
        
    d = definitions[0]
    print(f"Found: {d.name} (type: {d.type})")
    
    # Check bases
    try:
        print(f"Bases: {[b.name for b in d.bases()]}")
    except:
        print("Could not retrieve bases.")
    
    print("\nDocstring:")
    print(d.docstring())

if __name__ == "__main__":
    test_jedi_hover()
