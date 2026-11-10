from notes.models import Note, NotFound


def load_owned(store: dict[str, Note], user: str, note_id: str) -> Note:
    """The note, when it exists and belongs to `user`; NotFound otherwise."""
    note = store.get(note_id)
    if note is None or note.owner != user:
        raise NotFound(note_id)
    return note
