"""Writes small, valid sample files for the browser test: two text PDFs, a PNG and a refused .txt."""
import os
import struct
import sys
import zlib

out = sys.argv[1]
os.makedirs(out, exist_ok=True)


def pdf(text_lines):
    """A one-page PDF with real text, with a correct cross-reference table."""
    stream = "BT /F1 14 Tf 50 750 Td " + " ".join(f"({line}) Tj 0 -20 Td" for line in text_lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body = b"%PDF-1.4\n"
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{number} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        body += f"{offset:010d} 00000 n \n".encode()
    body += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return body


def png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * 8 for _ in range(8))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


files = {
    "Quyet dinh 123 ve luu tru.pdf": pdf(["Quyet dinh so 123 ve bao quan tai lieu luu tru", "Archive retention zebra policy"]),
    "Bao cao nam 2020.pdf": pdf(["Bao cao tong ket cong tac van thu luu tru nam 2020"]),
    "Anh scan trang 1.png": png(),
    "ghi chu.txt": b"plain text is not an accepted archive format",
}
for name, data in files.items():
    with open(os.path.join(out, name), "wb") as handle:
        handle.write(data)
print("made", ", ".join(files))
