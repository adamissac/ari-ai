from notes.models import Note, NotFound


def get_note(store: dict[str, Note], user: str, note_id: str) -> Note:
    note = store.get(note_id)
    if note is None or note.owner != user:
        raise NotFound(note_id)
    return note


def update_note(store: dict[str, Note], user: str, note_id: str, text: str) -> Note:
    note = store.get(note_id)
    if note is None or note.owner != user:
        raise NotFound(note_id)
    note.text = text
    return note
