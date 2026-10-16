#!/usr/bin/env python3
"""Build the Vietnamese user guide DOCX from its HTML source and local screenshots."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlparse
import re
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs/HUONG_DAN_SU_DUNG.html"
OUTPUT = ROOT / "docs/HUONG_DAN_SU_DUNG.docx"
ASSETS = ROOT / "docs/assets/huong-dan-su-dung"
RELS = "word/_rels/document.xml.rels"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
IMAGE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
IMAGE_WIDTH_EMU = 5_580_000  # 15.5 cm; LibreOffice ignores HTML/CSS image width on import
PORTRAIT_WIDTH_EMU = 4_320_000  # 12 cm; keep a full form and its caption on one A4 page


def fit_images(document_xml: bytes, widths: dict[str, int]) -> bytes:
    def resize_drawing(match: re.Match) -> bytes:
        drawing = match.group(0)
        relation = re.search(rb'r:embed="([^"]+)"', drawing)
        if not relation:
            raise RuntimeError("Ảnh không có relationship")
        image_id = relation.group(1).decode()
        width = widths[image_id]

        def resize_extent(extent: re.Match) -> bytes:
            original_width, original_height = int(extent.group(2)), int(extent.group(3))
            height = round(original_height * width / original_width)
            return b"<" + extent.group(1) + f' cx="{width}" cy="{height}"/>'.encode()

        drawing, count = re.subn(rb'<(wp:extent|a:ext) cx="(\d+)" cy="(\d+)"/>', resize_extent, drawing)
        if count != 2:
            raise RuntimeError(f"Ảnh {image_id} có {count} kích thước, cần 2")
        return drawing

    document_xml, count = re.subn(rb'<wp:inline\b.*?</wp:inline>', resize_drawing, document_xml, flags=re.S)
    if count != len(widths):
        raise RuntimeError(f"Cần {len(widths)} ảnh minh họa, tìm thấy {count}")
    return document_xml


def link_to_embed(document_xml: bytes, image_ids: list[str]) -> bytes:
    for image_id in image_ids:
        old = f'<a:blip r:link="{image_id}">'.encode()
        new = f'<a:blip r:embed="{image_id}">'.encode()
        if document_xml.count(old) != 1:
            raise RuntimeError(f"Không tìm thấy ảnh {image_id} trong nội dung DOCX")
        document_xml = document_xml.replace(old, new)
    return document_xml


def embed_images(converted: Path, output: Path) -> int:
    """LibreOffice links HTML images externally; package them inside the DOCX."""
    images = {}
    image_ids = []
    widths = {}
    with zipfile.ZipFile(converted) as source:
        relationships = ET.fromstring(source.read(RELS))
        for relation in relationships.findall(f"{{{REL_NS}}}Relationship"):
            if relation.get("Type") != IMAGE_REL or relation.get("TargetMode") != "External":
                continue
            path = Path(unquote(urlparse(relation.attrib["Target"]).path)).resolve()
            if ASSETS not in path.parents or not path.is_file():
                raise RuntimeError(f"Ảnh ngoài thư mục hướng dẫn: {path}")
            target = f"media/{path.name}"
            relation.set("Target", target)
            relation.attrib.pop("TargetMode", None)
            data = path.read_bytes()
            if data[:8] != b"\x89PNG\r\n\x1a\n":
                raise RuntimeError(f"Ảnh minh họa phải là PNG: {path}")
            width_px, height_px = struct.unpack(">II", data[16:24])
            image_id = relation.attrib["Id"]
            images[f"word/{target}"] = data
            image_ids.append(image_id)
            widths[image_id] = PORTRAIT_WIDTH_EMU if height_px > width_px else IMAGE_WIDTH_EMU

        if not images:
            raise RuntimeError("Không tìm thấy ảnh minh họa trong DOCX")
        ET.register_namespace("", REL_NS)
        with zipfile.ZipFile(output, "w") as document:
            for item in source.infolist():
                data = ET.tostring(relationships, encoding="utf-8", xml_declaration=True) if item.filename == RELS else source.read(item)
                if item.filename == "word/document.xml":
                    data = fit_images(link_to_embed(data, image_ids), widths)
                document.writestr(item, data)
            for name, data in images.items():
                document.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    return len(images)


def main() -> None:
    writer = shutil.which("lowriter") or shutil.which("libreoffice")
    if not writer:
        raise SystemExit("Cần cài LibreOffice Writer để tạo file DOCX")
    with TemporaryDirectory(prefix="dm-guide-") as directory:
        temp = Path(directory)
        subprocess.run(
            [writer, f"-env:UserInstallation={temp.joinpath('profile').as_uri()}", "--headless",
             "--convert-to", "docx:Office Open XML Text", "--outdir", str(temp), str(SOURCE)],
            check=True,
        )
        converted = temp / OUTPUT.name
        if not converted.is_file():
            raise RuntimeError("LibreOffice không tạo được file DOCX")
        count = embed_images(converted, OUTPUT)
    print(f"Đã tạo {OUTPUT} với {count} ảnh nhúng")


if __name__ == "__main__":
    main()
