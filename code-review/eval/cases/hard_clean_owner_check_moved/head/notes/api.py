from notes.access import load_owned
from notes.models import Note


def get_note(store: dict[str, Note], user: str, note_id: str) -> Note:
    return load_owned(store, user, note_id)


def update_note(store: dict[str, Note], user: str, note_id: str, text: str) -> Note:
    note = load_owned(store, user, note_id)
    note.text = text
    return note


def delete_note(store: dict[str, Note], user: str, note_id: str) -> None:
    del store[load_owned(store, user, note_id).id]
