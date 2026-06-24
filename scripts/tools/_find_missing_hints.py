"""Find functions missing return type annotations in target files."""
import ast
import os
from collections import defaultdict

# Forbidden files
forbidden = {
    'scripts/collaboration/models.py',
    'scripts/collaboration/models_base.py',
    'scripts/collaboration/models_dispatch.py',
    'scripts/collaboration/models_lifecycle.py',
    'scripts/collaboration/memory_bridge.py',
    'scripts/collaboration/memory_types.py',
    'scripts/collaboration/memory_serializer.py',
    'scripts/collaboration/memory_query.py',
}

# Target directories/files
targets = []
for root, dirs, files in os.walk('scripts'):
    dirs[:] = [d for d in dirs if d not in ['__pycache__', '_archived']]
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(root, f)
        # collaboration dir
        if path.startswith('scripts/collaboration/'):
            if path not in forbidden:
                targets.append(path)
        # cli*.py
        elif os.path.basename(path).startswith('cli') and path.startswith('scripts/') or path in ['scripts/api_server.py', 'scripts/dashboard.py']:
            targets.append(path)

missing_by_file = defaultdict(list)
for path in sorted(targets):
    with open(path) as fh:
        try:
            tree = ast.parse(fh.read())
        except Exception:
            continue
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is None:
            missing_by_file[path].append((node.lineno, node.name, type(node).__name__))

total_missing = sum(len(v) for v in missing_by_file.values())
print(f'Total missing in target files: {total_missing}')
print(f'Files with missing: {len(missing_by_file)}')
print()
for path, items in sorted(missing_by_file.items()):
    print(f'=== {path} ({len(items)} missing) ===')
    for ln, name, kind in items:
        print(f'  L{ln}: {kind} {name}')
    print()
