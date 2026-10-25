"""Additional review-only artifact disclosure probes with synthetic secrets."""
import pytest
from backend.artifacts import ArtifactStore
from backend.db import transaction
from shared.evidence import ArtifactKind

@pytest.mark.parametrize('source', [
    'settings = {"password": "review-only-dict-password"}\n',
    'password: str = "review-only-typed-password"\n',
])
def test_literal_secret_is_not_stored_in_redacted_diff(source, tmp_path):
    secret = 'review-only-dict-password' if 'dict-password' in source else 'review-only-typed-password'
    store = ArtifactStore(tmp_path.as_uri())
    with transaction() as conn:
        ref = store.put_text(conn, source, kind=ArtifactKind.diff, project_id=None)
    with transaction() as conn:
        row, body = store.get(conn, ref.id)
    assert row['redacted'] is True
    assert secret not in body.decode(), 'literal credential retained in artifact labeled redacted'
