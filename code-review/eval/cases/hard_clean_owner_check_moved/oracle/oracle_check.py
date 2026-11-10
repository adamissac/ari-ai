import pytest
from notes.api import delete_note, get_note, update_note
from notes.models import Note, NotFound


def test_another_user_can_do_nothing_with_the_note():
    store = {"n1": Note("n1", "alice", "hi")}
    for call in (
        lambda: get_note(store, "bob", "n1"),
        lambda: update_note(store, "bob", "n1", "x"),
        lambda: delete_note(store, "bob", "n1"),
    ):
        with pytest.raises(NotFound):
            call()
    assert store["n1"].text == "hi"


def test_owner_deletes():
    store = {"n1": Note("n1", "alice", "hi")}
    delete_note(store, "alice", "n1")
    assert store == {}
