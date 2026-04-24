import sys, os, importlib.util
spec_file = os.path.abspath("spec/main_spec.py")
cwd = os.getcwd()
if spec_file.startswith(cwd):
    rel_path = os.path.relpath(spec_file, cwd)
    module_name = os.path.splitext(rel_path)[0].replace(os.path.sep, '.')
    package_name = ".".join(module_name.split('.')[:-1])
    root_dir = cwd
else:
    root_dir = os.path.dirname(spec_file)
    module_name = os.path.splitext(os.path.basename(spec_file))[0]
    package_name = ""

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

loader = importlib.util.spec_from_file_location(module_name, spec_file)
module = importlib.util.module_from_spec(loader)
module.__name__ = module_name
module.__package__ = package_name
loader.loader.exec_module(module)
print("SUCCESS importing relative package!")
