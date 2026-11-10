from webhooks.consumer import Consumer


def test_a_repeat_in_the_same_batch_is_skipped():
    got = []
    consumer = Consumer(got.append)
    assert consumer.handle_batch([{"id": "e1"}, {"id": "e1"}, {"id": "e2"}]) == 2
    assert [e["id"] for e in got] == ["e1", "e2"]
