"""Vector icon set rendered from inline SVG (crisp at any DPI, no assets)."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'fill="none" stroke="{color}" stroke-width="{width}" '
    'stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
)

PATHS: dict[str, str] = {
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/>'
           '<circle cx="12" cy="12" r="3"/>',
    "eye_off": '<path d="M3 3l18 18"/>'
               '<path d="M10.6 5.2A10.9 10.9 0 0112 5c6.4 0 10 7 10 7a17 17 0 01-3.1 4"/>'
               '<path d="M6.6 6.6A17 17 0 002 12s3.6 7 10 7a10.5 10.5 0 004.1-.8"/>'
               '<path d="M9.9 9.9a3 3 0 104.2 4.2"/>',
    "copy": '<rect x="9" y="9" width="12" height="12" rx="2.5"/>'
            '<path d="M5 15H4a1 1 0 01-1-1V4a1 1 0 011-1h10a1 1 0 011 1v1"/>',
    "check": '<path d="M4 12.5l5 5L20 6.5"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.6-3.6"/>',
    "lock": '<rect x="4" y="10.5" width="16" height="10.5" rx="2.5"/>'
            '<path d="M8 10.5V7.5a4 4 0 018 0v3"/>',
    "unlock": '<rect x="4" y="10.5" width="16" height="10.5" rx="2.5"/>'
              '<path d="M8 10.5V7.5a4 4 0 017.5-2"/>',
    "settings": '<circle cx="12" cy="12" r="3.2"/>'
                '<path d="M19.4 14.6a1.7 1.7 0 00.3 1.9l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.9-.3 1.7 1.7 0 00-1 1.6v.2a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.6 1.7 1.7 0 00-1.9.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.9 1.7 1.7 0 00-1.6-1H2.7a2 2 0 110-4h.1a1.7 1.7 0 001.6-1.1 1.7 1.7 0 00-.3-1.9l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.9.3H9a1.7 1.7 0 001-1.6V2.7a2 2 0 114 0v.1a1.7 1.7 0 001 1.6 1.7 1.7 0 001.9-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.9V9a1.7 1.7 0 001.6 1h.2a2 2 0 110 4h-.1a1.7 1.7 0 00-1.6 1z"/>',
    "key": '<circle cx="8" cy="8" r="4.5"/><path d="M11.2 11.2L21 21M17 17l2-2M14 14l2-2"/>',
    "trash": '<path d="M3.5 6.5h17M9 6.5V4.8A1.8 1.8 0 0110.8 3h2.4A1.8 1.8 0 0115 4.8v1.7"/>'
             '<path d="M5.5 6.5l1 13a2 2 0 002 1.9h7a2 2 0 002-1.9l1-13"/>'
             '<path d="M10 11v6M14 11v6"/>',
    "edit": '<path d="M12 20h9"/>'
            '<path d="M16.5 3.5a2.1 2.1 0 013 3L7.5 18.5l-4 1 1-4z"/>',
    "shield": '<path d="M12 2.5l8 3v6c0 5-3.4 9-8 10.5C7.4 20.5 4 16.5 4 11.5v-6z"/>'
              '<path d="M9 12l2.2 2.2L15.5 10"/>',
    "refresh": '<path d="M20.5 12a8.5 8.5 0 11-2.6-6.1"/>'
               '<path d="M20.5 3.5V8H16"/>',
    "download": '<path d="M12 3v11"/><path d="M7.5 10L12 14.5 16.5 10"/>'
                '<path d="M4 17.5v1.7A1.8 1.8 0 005.8 21h12.4a1.8 1.8 0 001.8-1.8v-1.7"/>',
    "upload": '<path d="M12 14.5V3"/><path d="M7.5 7.5L12 3l4.5 4.5"/>'
              '<path d="M4 17.5v1.7A1.8 1.8 0 005.8 21h12.4a1.8 1.8 0 001.8-1.8v-1.7"/>',
    "folder": '<path d="M3 7.5A2 2 0 015 5.5h3.6l2 2.4H19a2 2 0 012 2v7.6a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>',
    "sparkles": '<path d="M12 3l1.9 4.9L19 9.8l-5.1 1.9L12 16.6l-1.9-4.9L5 9.8l5.1-1.9z"/>'
                '<path d="M18.5 15.5l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9z"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "chevron_down": '<path d="M6 9.5l6 6 6-6"/>',
    "globe": '<circle cx="12" cy="12" r="9"/>'
             '<path d="M3 12h18"/><path d="M12 3a14 14 0 010 18a14 14 0 010-18z"/>',
    "user": '<circle cx="12" cy="8" r="4"/>'
            '<path d="M4.5 21a7.5 7.5 0 0115 0"/>',
    "tag": '<path d="M20.5 13.5l-7 7a2 2 0 01-2.8 0l-7.2-7.2a2 2 0 01-.6-1.4V4.5a1.5 1.5 0 011.5-1.5h7.4a2 2 0 011.4.6l7.3 7.3a2 2 0 010 2.6z"/>'
           '<circle cx="8" cy="8" r="1.4"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5.5l3.5 2"/>',
    "alert": '<path d="M10.3 3.9L2.5 17.4A1.9 1.9 0 004.2 20.3h15.6a1.9 1.9 0 001.7-2.9L13.7 3.9a1.9 1.9 0 00-3.4 0z"/>'
             '<path d="M12 9v4.5"/><path d="M12 17h.01"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/><path d="M12 7.8h.01"/>',
    "save": '<path d="M4 5.5A1.5 1.5 0 015.5 4h10L20 8.5v10a1.5 1.5 0 01-1.5 1.5h-13A1.5 1.5 0 014 18.5z"/>'
            '<path d="M8 4v5h7V4"/><path d="M8 20v-6h8v6"/>',
    "note": '<path d="M5 4.5A1.5 1.5 0 016.5 3h11A1.5 1.5 0 0119 4.5v15a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 015 19.5z"/>'
            '<path d="M8.5 8h7M8.5 12h7M8.5 16h4"/>',
    "database": '<ellipse cx="12" cy="6" rx="8" ry="3"/>'
                '<path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/>'
                '<path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "arrow_right": '<path d="M5 12h14"/><path d="M13 6l6 6-6 6"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "heart": '<path d="M12 20s-8-4.7-8-10a4.6 4.6 0 018-3 4.6 4.6 0 018 3c0 5.3-8 10-8 10z"/>',
    "external": '<path d="M14 4h6v6"/><path d="M20 4L11 13"/>'
                '<path d="M18 14v4.5A1.5 1.5 0 0116.5 20h-11A1.5 1.5 0 014 18.5v-11A1.5 1.5 0 015.5 6H10"/>',
    "sun": '<circle cx="12" cy="12" r="4"/>'
           '<path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/>',
}

_cache: dict[tuple[str, str, int], QIcon] = {}


def icon(name: str, color: str = "#ffffff", size: int = 18, width: float = 1.9) -> QIcon:
    key = (name, color, size)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    body = PATHS.get(name)
    if not body:
        return QIcon()
    svg = _SVG.format(color=color, width=width, body=body)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    ratio = 2
    pixmap = QPixmap(size * ratio, size * ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size * ratio, size * ratio))
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    result = QIcon(pixmap)
    _cache[key] = result
    return result


def clear_cache() -> None:
    _cache.clear()
