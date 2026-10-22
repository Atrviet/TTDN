from uuid import uuid4

from app.ai.rag.chunker import DocumentChunker


def test_chunking_preserves_page_metadata_and_vietnamese_unicode() -> None:
    document_id = uuid4()
    chunker = DocumentChunker(chunk_size=5, overlap=2)
    pages = [
        {"page_number": 1, "text": "CHƯƠNG 1\nTrí tuệ nhân tạo hỗ trợ học tập."},
        {"page_number": 2, "text": "Nội dung trang thứ hai."},
    ]

    chunks = chunker.chunk_pages(document_id, pages)

    assert chunks
    assert all(chunk.document_id == document_id for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert {chunk.page_number for chunk in chunks} == {1, 2}
    assert "CHƯƠNG 1\nTrí" in chunks[0].text
    assert all(chunk.token_count <= 5 for chunk in chunks)


def test_chunk_overlap_repeats_configured_token_window() -> None:
    chunks = DocumentChunker(chunk_size=4, overlap=2).chunk_pages(
        uuid4(),
        [{"page_number": 1, "text": "một hai ba bốn năm sáu"}],
    )

    assert [chunk.text for chunk in chunks] == ["một hai ba bốn", "ba bốn năm sáu"]
    assert [chunk.token_count for chunk in chunks] == [4, 4]


def test_empty_pages_are_skipped() -> None:
    chunks = DocumentChunker(chunk_size=10, overlap=2).chunk_pages(
        uuid4(),
        [{"page_number": 1, "text": ""}, {"page_number": 2, "text": "Nội dung"}],
    )

    assert len(chunks) == 1
    assert chunks[0].page_number == 2

