"""Pure-Python SVG barcode and shelf label generator for library physical copies.

Implements Code 39 encoding without any external dependencies, producing
lightweight, resolution-independent SVG markup for display, scanning, and printing.
"""

from html import escape

# Standard Code 39 character patterns (1 = wide bar/space, 0 = narrow bar/space)
# Each pattern contains 9 elements: 5 bars and 4 spaces alternating (b s b s b s b s b)
CODE39_PATTERNS = {
    '0': '000110100', '1': '100100001', '2': '001100001', '3': '101100000',
    '4': '000110001', '5': '100110000', '6': '001110000', '7': '000100101',
    '8': '100100100', '9': '001100100', 'A': '100001001', 'B': '001001001',
    'C': '101001000', 'D': '000011001', 'E': '100011000', 'F': '001011000',
    'G': '000001101', 'H': '100001100', 'I': '001001100', 'J': '000011100',
    'K': '100000011', 'L': '001000011', 'M': '101000010', 'N': '000010011',
    'O': '100010010', 'P': '001010010', 'Q': '000000111', 'R': '100000110',
    'S': '001000110', 'T': '000010110', 'U': '110000001', 'V': '011000001',
    'W': '111000000', 'X': '010010001', 'Y': '110010000', 'Z': '011010000',
    '-': '010000101', '.': '110000100', ' ': '011000100', '$': '010101000',
    '/': '010100010', '+': '010001010', '%': '000101010', '*': '010010100',
}


def sanitize_barcode(text: str) -> str:
    """Normalize input text for Code 39 encoding, defaulting invalid chars to dashes."""
    normalized = text.strip().upper()
    return "".join(c if c in CODE39_PATTERNS and c != '*' else '-' for c in normalized)


def generate_code39_svg(
    text: str,
    bar_height: int = 50,
    narrow_width: int = 2,
    wide_width: int = 5,
    quiet_zone: int = 15,
    show_text: bool = True,
    text_size: int = 13,
) -> str:
    """Generate a valid standalone SVG representation of a Code 39 barcode.

    :param text: Barcode string to encode (alphanumeric and standard punctuation).
    :param bar_height: Height in pixels of the barcode bars.
    :param narrow_width: Width in pixels of narrow bars/spaces.
    :param wide_width: Width in pixels of wide bars/spaces.
    :param quiet_zone: Padding in pixels on the left and right margins.
    :param show_text: If True, include a human-readable text label below bars.
    :param text_size: Font size for the human-readable text.
    :return: An XML string with the complete SVG document or fragment.
    """
    clean_text = sanitize_barcode(text)
    if not clean_text:
        clean_text = "EMPTY"

    full_payload = f"*{clean_text}*"
    inter_char_gap = narrow_width

    # Pre-calculate full width
    total_width = quiet_zone * 2
    for i, char in enumerate(full_payload):
        pattern = CODE39_PATTERNS.get(char, CODE39_PATTERNS['-'])
        for element_idx, bit in enumerate(pattern):
            is_bar = (element_idx % 2 == 0)
            element_width = wide_width if bit == '1' else narrow_width
            total_width += element_width
        if i < len(full_payload) - 1:
            total_width += inter_char_gap

    text_margin = text_size + 8 if show_text else 0
    total_height = bar_height + text_margin + 12

    # Draw SVG rect elements
    rects = []
    current_x = quiet_zone
    top_y = 6

    for i, char in enumerate(full_payload):
        pattern = CODE39_PATTERNS.get(char, CODE39_PATTERNS['-'])
        for element_idx, bit in enumerate(pattern):
            is_bar = (element_idx % 2 == 0)
            element_width = wide_width if bit == '1' else narrow_width
            if is_bar:
                rects.append(
                    f'<rect x="{current_x}" y="{top_y}" width="{element_width}" '
                    f'height="{bar_height}" fill="#1e293b" />'
                )
            current_x += element_width
        if i < len(full_payload) - 1:
            current_x += inter_char_gap

    text_element = ""
    if show_text:
        text_y = top_y + bar_height + text_size + 2
        center_x = total_width // 2
        text_element = (
            f'<text x="{center_x}" y="{text_y}" font-family="ui-monospace, monospace, monospace" '
            f'font-size="{text_size}" font-weight="600" text-anchor="middle" fill="#0f172a" '
            f'letter-spacing="2">{escape(clean_text)}</text>'
        )

    svg_content = "\n  ".join(rects)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_width} {total_height}" '
        f'width="{total_width}" height="{total_height}" role="img" aria-label="Barcode {escape(clean_text)}">\n'
        f'  <style>rect {{ shape-rendering: crispEdges; }}</style>\n'
        f'  <rect width="100%" height="100%" fill="#ffffff" rx="4" />\n'
        f'  {svg_content}\n'
        f'  {text_element}\n'
        f'</svg>'
    )


def generate_shelf_label_svg(
    barcode: str,
    title: str,
    shelf_location: str = "General Stacks",
    copy_number: int = 1,
) -> str:
    """Generate a printable 300x160 physical inventory shelf label."""
    clean_barcode = sanitize_barcode(barcode)
    safe_title = escape(title[:36] + ("..." if len(title) > 36 else ""))
    safe_location = escape(shelf_location[:24])
    barcode_svg = generate_code39_svg(clean_barcode, bar_height=40, narrow_width=2, wide_width=4, show_text=False)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180" width="320" height="180" '
        f'style="background:#fff; border:1px solid #cbd5e1; border-radius:8px; font-family:sans-serif;">\n'
        f'  <rect width="100%" height="100%" fill="#ffffff" rx="8" />\n'
        f'  <rect x="0" y="0" width="320" height="28" fill="#047857" rx="8" />\n'
        f'  <rect x="0" y="20" width="320" height="8" fill="#047857" />\n'
        f'  <text x="12" y="19" font-size="12" font-weight="bold" fill="#ffffff">CAMPUS CENTRAL LIBRARY</text>\n'
        f'  <text x="308" y="19" font-size="11" font-weight="600" text-anchor="end" fill="#a7f3d0">COPY #{copy_number}</text>\n'
        f'  <text x="14" y="48" font-size="13" font-weight="bold" fill="#0f172a">{safe_title}</text>\n'
        f'  <text x="14" y="65" font-size="11" fill="#64748b">Location: <tspan font-weight="600" fill="#0f172a">{safe_location}</tspan></text>\n'
        f'  <g transform="translate(15, 75)">\n'
        f'    {barcode_svg}\n'
        f'  </g>\n'
        f'  <text x="160" y="165" font-size="11" font-family="monospace" font-weight="600" text-anchor="middle" fill="#334155">{escape(clean_barcode)}</text>\n'
        f'</svg>'
    )
