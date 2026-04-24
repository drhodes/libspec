import sys, os, importlib
spec_file = os.path.abspath("spec/main_spec.py")
cwd = os.getcwd()
if spec_file.startswith(cwd):
    rel_path = os.path.relpath(spec_file, cwd)
    module_name = os.path.splitext(rel_path)[0].replace(os.path.sep, '.')
else:
    module_name = os.path.splitext(os.path.basename(spec_file))[0]

if cwd not in sys.path:
    sys.path.insert(0, cwd)

module = importlib.import_module(module_name)
print(f"module name: {module.__name__}, package: {module.__package__}")
