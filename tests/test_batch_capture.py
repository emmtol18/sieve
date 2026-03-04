from sieve.api.capsules.schemas import BatchCaptureItem, BatchCaptureRequest


def test_batch_capture_item_schema():
    item = BatchCaptureItem(content="tweet text", source_url="https://x.com/user/status/123")
    assert item.content == "tweet text"
    assert item.source_url == "https://x.com/user/status/123"


def test_batch_capture_item_source_url_optional():
    item = BatchCaptureItem(content="tweet text")
    assert item.source_url is None


def test_batch_capture_request_schema():
    req = BatchCaptureRequest(
        items=[
            BatchCaptureItem(content="tweet 1"),
            BatchCaptureItem(content="tweet 2"),
        ],
        creator_id="abc-123",
    )
    assert len(req.items) == 2
    assert req.creator_id == "abc-123"
    assert req.source_type == "tweet"


def test_batch_capture_request_source_type_default():
    req = BatchCaptureRequest(
        items=[BatchCaptureItem(content="tweet")],
        creator_id="abc",
    )
    assert req.source_type == "tweet"
