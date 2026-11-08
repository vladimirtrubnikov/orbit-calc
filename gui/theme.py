"""gui/theme.py — QSS и палитра."""
from PySide6.QtGui import QColor, QPalette


def apply_theme(app) -> None:
    app.setStyle("Fusion")
    p = app.palette()
    p.setColor(QPalette.Window, QColor("#0f0f18"))
    p.setColor(QPalette.WindowText, QColor("#d4d4d4"))
    p.setColor(QPalette.Base, QColor("#12121c"))
    p.setColor(QPalette.AlternateBase, QColor("#1a1a2e"))
    p.setColor(QPalette.Text, QColor("#d4d4d4"))
    p.setColor(QPalette.Button, QColor("#2a2a3a"))
    p.setColor(QPalette.ButtonText, QColor("#d4d4d4"))
    p.setColor(QPalette.Highlight, QColor("#8b5cf6"))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.ToolTipBase, QColor("#1a1a2e"))
    p.setColor(QPalette.ToolTipText, QColor("#d4d4d4"))
    app.setPalette(p)

    app.setStyleSheet("""
    QToolBar { background:#15151f; border:none; padding:4px; spacing:6px; }
    QPushButton {
        background:#2a2a3a; color:#d4d4d4;
        border:1px solid #3a3a4a; border-radius:6px;
        padding:6px 14px; font-size:12px;
    }
    QPushButton:hover { background:#3a3a4a; }
    QPushButton:pressed { background:#8b5cf6; }
    QPushButton#primary {
        background:#8b5cf6; color:white;
        border:none; font-weight:bold;
    }
    QPushButton#primary:hover { background:#9d6bff; }
    QSplitter::handle { background:#1a1a2e; width:2px; }
    QStatusBar { background:#15151f; color:#888; }
    QScrollBar:vertical { background:#12121c; width:10px; border:none; }
    QScrollBar::handle:vertical { background:#3a3a4a; border-radius:5px; min-height:20px; }
    QScrollBar::handle:vertical:hover { background:#8b5cf6; }
    """)
