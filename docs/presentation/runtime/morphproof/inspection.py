"""Bounded source inventory. Reads project source, never executes it."""
import ast
import os
from pathlib import Path
import sys


def inspect_repository(root: Path, max_files=500) -> dict:
    root=Path(root).resolve()
    if not root.is_dir():
        raise ValueError('Repository must be an existing directory')
    result={'schema':1,'root':str(root),'modules':[],'tests':[],'documentation':[],
            'dependency_manifests':[],'limits':['Read-only inventory; existing tests are discovered, not executed.',
            'At most 500 Python files and 1 MiB per source file; hidden directories, environments and build outputs skipped.'],
            'skipped':[]}
    excluded={'target','node_modules','venv','.venv','build','dist','__pycache__','runs'}
    count=0
    for directory,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=sorted(d for d in dirs if not d.startswith('.') and d not in excluded and not (Path(directory)/d).is_symlink())
        for name in sorted(files):
            path=Path(directory)/name
            if path.is_symlink(): continue
            relative=path.relative_to(root).as_posix()
            if name in {'pyproject.toml','requirements.txt','Cargo.toml','Cargo.lock','poetry.lock','uv.lock','setup.cfg'}:
                result['dependency_manifests'].append(relative)
            if name.lower().startswith(('readme','changelog')) or (name.endswith('.md') and 'docs' in path.relative_to(root).parts):
                result['documentation'].append(relative)
            if not name.endswith('.py'): continue
            count+=1
            if count>max_files:
                result['skipped'].append('Python file inventory cap reached')
                return result
            if path.stat().st_size>1024*1024:
                result['skipped'].append(relative+': larger than 1 MiB');continue
            if name.startswith('test_') or name.endswith('_test.py'):
                result['tests'].append(relative)
            try: tree=ast.parse(path.read_text(encoding='utf-8'))
            except (SyntaxError,UnicodeError,OSError) as exc:
                result['skipped'].append(relative+': '+type(exc).__name__);continue
            functions=[]
            for item in tree.body:
                if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)) and not item.name.startswith('_'):
                    functions.append({'name':item.name,'parameters':[a.arg for a in item.args.args],
                                      'documentation':ast.get_docstring(item),'line':item.lineno})
            if functions:
                result['modules'].append({'path':relative,'functions':functions})
    return result
