import pytest
from notes.api import get_note, update_note
from notes.models import Note, NotFound


def test_owner_reads_and_edits():
    store = {"n1": Note("n1", "alice", "hi")}
    assert get_note(store, "alice", "n1").text == "hi"
    assert update_note(store, "alice", "n1", "bye").text == "bye"


def test_missing_note():
    with pytest.raises(NotFound):
        get_note({}, "alice", "n1")
