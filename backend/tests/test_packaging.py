"""Guards the gap between the dev environment and the shipped image.

The Docker image installs only `[project] dependencies` (see
backend/Dockerfile's `pip install .`), while the dev venv additionally has the
`dev` extra and its transitive packages. A module-scope import of something
that's only present in dev therefore passes every unit test and then crashes
the container on startup -- which is exactly what happened when
`zgrader.analysis.ai` imported `httpx` (a TestClient dev dependency) at module
level and took the whole backend down.

This test asserts that every third-party module imported at module scope
anywhere in `zgrader/` is declared as a runtime dependency.
"""

import ast
import pathlib
import sys
import tomllib

BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE_ROOT = BACKEND_ROOT / "zgrader"

# Import name -> distribution name, for the cases where they differ.
_IMPORT_TO_DISTRIBUTION = {
    "cv2": "opencv-python-headless",
    "PIL": "pillow",
    "jwt": "pyjwt",
    "skimage": "scikit-image",
    "yaml": "pyyaml",
    "dateutil": "python-dateutil",
    "multipart": "python-multipart",
    "email_validator": "email-validator",
    "pydantic_settings": "pydantic-settings",
    "sqlalchemy": "sqlalchemy",
    "weasyprint": "weasyprint",
}


def _declared_runtime_distributions() -> set[str]:
    with open(BACKEND_ROOT / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    names = set()
    for spec in pyproject["project"]["dependencies"]:
        # "uvicorn[standard]>=0.32" -> "uvicorn"
        name = spec.split("[")[0]
        for sep in (">=", "<=", "==", "!=", "~=", ">", "<", ";"):
            name = name.split(sep)[0]
        names.add(name.strip().lower().replace("_", "-"))
    return names


def _module_scope_imports(tree: ast.AST) -> set[str]:
    """Top-level module names imported at module scope (not inside a function
    or method -- those are lazy and only need the package when actually
    called, which is how the optional AI seam is allowed to use httpx)."""
    found = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return found


def test_module_scope_imports_are_declared_runtime_dependencies():
    declared = _declared_runtime_distributions()
    stdlib = set(sys.stdlib_module_names)
    offenders: list[str] = []

    for path in PACKAGE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for module in _module_scope_imports(tree):
            if module == "zgrader" or module in stdlib or module.startswith("_"):
                continue
            distribution = _IMPORT_TO_DISTRIBUTION.get(module, module).lower().replace("_", "-")
            if distribution not in declared:
                offenders.append(f"{path.relative_to(BACKEND_ROOT)}: imports '{module}' ({distribution})")

    assert not offenders, (
        "Module-scope imports not declared in [project] dependencies -- these would crash the "
        "production image, which installs only the runtime dependency list:\n  "
        + "\n  ".join(sorted(offenders))
    )
