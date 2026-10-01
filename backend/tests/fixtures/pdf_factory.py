"""Programmatic PDF fixture factory for testing.

All test PDFs are generated at test-time using PyMuPDF — no binary blobs
checked into the repository.
"""

import pymupdf


def make_text_pdf(text: str = "Hello World — this is a test paragraph with enough content.", pages: int = 1) -> bytes:
    """Create a simple PDF with text content on each page."""
    doc = pymupdf.open()
    for page_num in range(pages):
        page = doc.new_page()
        page_text = f"Page {page_num + 1}: {text}"
        page.insert_text((72, 72), page_text, fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def make_multiblock_pdf() -> bytes:
    """Create a PDF with multiple text blocks on the same page."""
    doc = pymupdf.open()
    page = doc.new_page()

    # Write blocks at different positions so PyMuPDF treats them as
    # separate blocks in the layout.
    blocks = [
        "This is the first text block containing enough characters for extraction.",
        "Second block with different content, also exceeding the minimum length threshold.",
        "A third block placed at the bottom of the page with plenty of meaningful text content.",
    ]
    y_positions = [72, 200, 400]
    for text, y in zip(blocks, y_positions):
        page.insert_text((72, y), text, fontsize=11)

    data = doc.tobytes()
    doc.close()
    return data


def make_short_text_pdf() -> bytes:
    """Create a PDF with text too short to pass the minimum threshold."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hi", fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def make_empty_pdf() -> bytes:
    """Create an empty PDF (no text, tables, or images)."""
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


def make_image_pdf(width: int = 100, height: int = 100) -> bytes:
    """Create a PDF with an embedded raster image.

    Generates a small solid-color PNG and embeds it.
    """
    doc = pymupdf.open()
    page = doc.new_page()

    # Add some text so the page isn't entirely empty
    page.insert_text((72, 72), "Page with embedded image for extraction testing purposes.", fontsize=11)

    # Create a small image pixmap and insert it
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height), 1)
    pix.set_rect(pix.irect, (0, 100, 200, 255))  # fill blue (RGBA — alpha channel present)
    img_bytes = pix.tobytes("png")

    rect = pymupdf.Rect(72, 100, 72 + width, 100 + height)
    page.insert_image(rect, stream=img_bytes)

    data = doc.tobytes()
    doc.close()
    return data


def make_tiny_image_pdf() -> bytes:
    """Create a PDF with a tiny image (below MIN_IMAGE_DIMENSION threshold)."""
    return make_image_pdf(width=10, height=10)


def make_table_pdf() -> bytes:
    """Create a PDF with a simple table drawn using lines.

    pdfplumber detects tables from visual grid lines, so we draw
    a basic table structure using PyMuPDF's drawing primitives.
    """
    doc = pymupdf.open()
    page = doc.new_page()

    page.insert_text((72, 50), "Document with a table below for extraction testing.", fontsize=11)

    # Draw a simple 3×3 table with proper grid lines
    x0, y0 = 72, 80
    col_width = 120
    row_height = 25
    cols = 3
    rows = 4  # 1 header + 3 body

    # Draw horizontal lines
    for r in range(rows + 1):
        y = y0 + r * row_height
        shape = page.new_shape()
        shape.draw_line((x0, y), (x0 + cols * col_width, y))
        shape.finish(width=1)
        shape.commit()

    # Draw vertical lines
    for c in range(cols + 1):
        x = x0 + c * col_width
        shape = page.new_shape()
        shape.draw_line((x, y0), (x, y0 + rows * row_height))
        shape.finish(width=1)
        shape.commit()

    # Insert cell text
    cell_data = [
        ["Name", "Age", "City"],
        ["Alice", "30", "London"],
        ["Bob", "25", "Paris"],
        ["Carol", "35", "Tokyo"],
    ]
    for r, row in enumerate(cell_data):
        for c, val in enumerate(row):
            x = x0 + c * col_width + 5
            y = y0 + r * row_height + 17
            page.insert_text((x, y), val, fontsize=10)

    data = doc.tobytes()
    doc.close()
    return data


def make_multipage_pdf(num_pages: int = 5) -> bytes:
    """Create a multi-page PDF with distinct content per page."""
    doc = pymupdf.open()
    for i in range(num_pages):
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            f"Page {i + 1} of {num_pages}: This page contains enough text content "
            f"to pass the minimum character threshold for evidence extraction.",
            fontsize=11,
        )
    data = doc.tobytes()
    doc.close()
    return data


def make_mixed_content_pdf() -> bytes:
    """Create a PDF with text, an image, and table lines on the same page."""
    doc = pymupdf.open()
    page = doc.new_page()

    # Text
    page.insert_text(
        (72, 50),
        "This is a mixed-content page with text, images, and tables for comprehensive testing.",
        fontsize=11,
    )

    # Image
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 80, 80), 1)
    pix.set_rect(pix.irect, (255, 0, 0, 255))  # red (RGBA)
    img_bytes = pix.tobytes("png")
    page.insert_image(pymupdf.Rect(72, 100, 152, 180), stream=img_bytes)

    # Simple table lines
    x0, y0 = 72, 220
    col_w, row_h = 100, 20
    for r in range(3):
        y = y0 + r * row_h
        shape = page.new_shape()
        shape.draw_line((x0, y), (x0 + 2 * col_w, y))
        shape.finish(width=1)
        shape.commit()
    for c in range(3):
        x = x0 + c * col_w
        shape = page.new_shape()
        shape.draw_line((x, y0), (x, y0 + 2 * row_h))
        shape.finish(width=1)
        shape.commit()

    # Cell text for the table
    page.insert_text((x0 + 5, y0 + 15), "Col A", fontsize=9)
    page.insert_text((x0 + col_w + 5, y0 + 15), "Col B", fontsize=9)
    page.insert_text((x0 + 5, y0 + row_h + 15), "Val 1", fontsize=9)
    page.insert_text((x0 + col_w + 5, y0 + row_h + 15), "Val 2", fontsize=9)

    data = doc.tobytes()
    doc.close()
    return data
