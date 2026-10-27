from pathlib import Path
import tempfile
from morphproof.inspection import inspect_repository


def test_repository_inventory_skips_environment_and_linked_source():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);(root/'core.py').write_text('def energy(values):\n """Ordered reduction."""\n return 0.0\n')
        (root/'test_core.py').write_text('def test_energy(): pass')
        (root/'pyproject.toml').write_text('[project]\nname="example"')
        (root/'.venv').mkdir();(root/'.venv/hidden.py').write_text('def hidden(x): pass')
        (root/'linked.py').symlink_to(root/'core.py')
        data=inspect_repository(root)
        assert data['tests']==['test_core.py']
        assert data['dependency_manifests']==['pyproject.toml']
        assert [x['path'] for x in data['modules']]==['core.py','test_core.py']
        assert data['modules'][0]['functions'][0]['documentation']=='Ordered reduction.'
