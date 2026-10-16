#!/usr/bin/env python3
"""Build the Vietnamese user guide DOCX from its HTML source and local screenshots."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlparse
import re
import shutil
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
IMAGE_WIDTH_EMU = 3_960_000  # 11 cm; LibreOffice ignores HTML/CSS image width on import


def fit_images(document_xml: bytes, image_count: int) -> bytes:
    def resize(match: re.Match) -> bytes:
        original_width, original_height = int(match.group(2)), int(match.group(3))
        height = round(original_height * IMAGE_WIDTH_EMU / original_width)
        return b"<" + match.group(1) + f' cx="{IMAGE_WIDTH_EMU}" cy="{height}"/>'.encode()

    document_xml, count = re.subn(rb'<(wp:extent|a:ext) cx="(\d+)" cy="(\d+)"/>', resize, document_xml)
    if count != image_count * 2:
        raise RuntimeError(f"Cần {image_count} ảnh minh họa, tìm thấy {count // 2}")
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
            images[f"word/{target}"] = path.read_bytes()
            image_ids.append(relation.attrib["Id"])

        if not images:
            raise RuntimeError("Không tìm thấy ảnh minh họa trong DOCX")
        ET.register_namespace("", REL_NS)
        with zipfile.ZipFile(output, "w") as document:
            for item in source.infolist():
                data = ET.tostring(relationships, encoding="utf-8", xml_declaration=True) if item.filename == RELS else source.read(item)
                if item.filename == "word/document.xml":
                    data = fit_images(link_to_embed(data, image_ids), len(image_ids))
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
