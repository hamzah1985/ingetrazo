# SPDX-License-Identifier: GPL-3.0-or-later
"""Render the actual before/after pencil cursors for review.

Run from a checkout of the proposed revision:
    python scripts/render_pencil_cursor_comparison.py --before-ref origin/main

No application settings are read or changed. Both revisions use the same
palette, accent, cursor size and magnification.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import types


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    before = parser.add_mutually_exclusive_group()
    before.add_argument('--before-ref', help='Git ref for the previous icons.py')
    before.add_argument('--before-file', type=Path, help='Previously saved icons.py')
    parser.add_argument('--output-dir', type=Path, default=root / 'docs' / 'images')
    parser.add_argument('--font', type=Path, help='Optional font file for labels')
    args = parser.parse_args()
    if args.before_file:
        before_source = args.before_file.read_text(encoding='utf-8')
    else:
        before_source = subprocess.check_output(
            ['git', 'show', f'{args.before_ref or "origin/main"}:views/icons.py'],
            cwd=root, encoding='utf-8')
    after_source = (root / 'views' / 'icons.py').read_text(encoding='utf-8')

    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    os.environ.setdefault('QT_SCALE_FACTOR', '1')
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    font_path = args.font or next((path for path in (
        Path('C:/Windows/Fonts/segoeui.ttf'),
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
        Path('/System/Library/Fonts/Supplemental/Arial.ttf'),
    ) if path.is_file()), None)
    font_family = QFontDatabase.systemFont(QFontDatabase.GeneralFont).family()
    if font_path:
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            font_family = families[0]

    def load_icons(source: str, name: str):
        module = types.ModuleType(name)
        exec(compile(source, f'<{name}>', 'exec'), vars(module))
        return module

    def panel(source: str, title: str, caption: str) -> QImage:
        module = load_icons(source, title.lower())
        image = QImage(320, 402, QImage.Format_ARGB32)
        image.fill(QColor('#f7f8fa'))
        painter = QPainter(image)
        painter.setPen(QColor('#20262e'))
        font = QFont(font_family)
        font.setPixelSize(21)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(0, 5, 320, 28), Qt.AlignCenter, title)
        font.setPixelSize(13)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(QRectF(0, 34, 320, 22), Qt.AlignCenter, caption)

        for top, background, ink, label in (
            (68, '#ccccc9', '#232629', 'Light theme'),
            (236, '#262a30', '#e5e7eb', 'Dark theme'),
        ):
            painter.fillRect(QRectF(0, top, 320, 154), QColor(background))
            module._ink = lambda color=ink: QColor(color)
            module._accent = lambda: QColor('#3584e4')
            module.clear_cursor_cache()
            cursor = module.tool_cursor('line')
            raster = cursor.pixmap().toImage()
            painter.setPen(QColor(ink))
            painter.drawText(QRectF(12, top + 8, 130, 20), label)
            painter.drawImage(QRectF(40, top + 48, 32, 32), raster)
            painter.drawText(QRectF(12, top + 91, 95, 20), Qt.AlignCenter, '32 px')
            painter.drawText(QRectF(12, top + 116, 120, 20), 'Detail at 4x  →')
            painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
            painter.drawImage(QRectF(173, top + 17, 128, 128), raster)
        painter.end()
        return image

    before_image = panel(before_source, 'Before', 'Broad outline and flat barrel end')
    after_image = panel(after_source, 'After', 'Slim barrel, wood and graphite tip')
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    before_image.save(str(output / 'pencil-cursor-before.png'))
    after_image.save(str(output / 'pencil-cursor-after.png'))
    comparison = QImage(656, 402, QImage.Format_ARGB32)
    comparison.fill(QColor('#f7f8fa'))
    painter = QPainter(comparison)
    painter.drawImage(0, 0, before_image)
    painter.drawImage(336, 0, after_image)
    painter.end()
    comparison.save(str(output / 'pencil-cursor-comparison.png'))
    print(output / 'pencil-cursor-comparison.png')


if __name__ == '__main__':
    main()
