"""Repository publication/privacy tests."""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def test_repository_contains_no_local_deployment_data():
    """No public candidate contains known local identifiers or secrets."""
    script = Path(__file__).parents[1] / "scripts" / "check_publication.py"
    spec = spec_from_file_location("publication_audit_test", script)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    assert module.audit() == []
