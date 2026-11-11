from webhooks.consumer import Consumer


def test_every_event_reaches_the_handler():
    got = []
    consumer = Consumer(got.append)
    assert consumer.handle_batch([{"id": "e1"}, {"id": "e2"}]) == 2
    assert [e["id"] for e in got] == ["e1", "e2"]
    assert consumer.handled == 2
