import sys
import re
from pathlib import Path

def bump_version(component):
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("Error: pyproject.toml not found")
        sys.exit(1)

    content = pyproject_path.read_text()
    
    # Match the version string in [project] section
    # This regex is slightly more specific than the one in settings.py to avoid accidental matches
    match = re.search(r'(\[project\][^\[]*version\s*=\s*")([^"]+)(")', content, re.DOTALL)
    if not match:
        # Fallback to simple version at top if not found in [project]
        match = re.search(r'(^version\s*=\s*")([^"]+)(")', content, re.MULTILINE)
    
    if not match:
        print("Error: Could not find version in pyproject.toml")
        sys.exit(1)

    prefix, version_str, suffix = match.groups()
    parts = list(map(int, version_str.split('.')))

    if component == "major":
        parts[0] += 1
        parts[1] = 0
        parts[2] = 0
    elif component == "minor":
        parts[1] += 1
        parts[2] = 0
    elif component == "patch":
        parts[2] += 1
    else:
        print(f"Error: Invalid component '{component}'")
        sys.exit(1)

    new_version = ".".join(map(str, parts))
    new_content = content[:match.start()] + prefix + new_version + suffix + content[match.end():]
    
    pyproject_path.write_text(new_content)
    print(f"Bumped version from {version_str} to {new_version}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python bump_version.py [major|minor|patch]")
        sys.exit(1)
    bump_version(sys.argv[1])
