from webhooks.consumer import Consumer


def test_an_event_redelivered_in_a_later_batch_is_handled_once():
    got = []
    consumer = Consumer(got.append)
    consumer.handle_batch([{"id": "e1"}])
    consumer.handle_batch([{"id": "e1"}, {"id": "e2"}])
    assert [e["id"] for e in got] == ["e1", "e2"]
