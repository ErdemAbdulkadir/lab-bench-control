# Soft Dark / Modern Graphite — İterasyon 2
APP_QSS = """
QWidget {
    background-color: #2B3038;
    color: #E5EAF1;
    font-family: "Segoe UI";
    font-size: 10.5pt;
}
QMainWindow, QTabWidget::pane {
    background-color: #2B3038;
    border: none;
}

/* ---- Sekmeler ---- */
QTabWidget::tab-bar { left: 8px; }
QTabBar::tab {
    background: #343B45;
    color: #B4BECC;
    padding: 9px 30px;
    border: 1px solid #4B5665;
    border-bottom: none;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    margin-right: 3px;
    font-weight: 600;
    font-size: 10.5pt;
}
QTabBar::tab:selected {
    background: #3B434E;
    color: #E5EAF1;
    border-bottom: 2px solid #69A9F5;
}
QTabBar::tab:hover:!selected { background: #3B434E; }

/* ---- Paneller ---- */
QGroupBox {
    background-color: #343B45;
    border: 1px solid #4B5665;
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-weight: 600;
    font-size: 10.5pt;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    top: 0px;
    padding: 0 6px;
    color: #69A9F5;
    font-weight: 600;
    letter-spacing: 0.5px;
}

/* ---- Giriş alanları ---- */
QComboBox, QDoubleSpinBox, QLineEdit, QSpinBox {
    background-color: #2B313A;
    border: 1px solid #4B5665;
    border-radius: 6px;
    padding: 6px 9px;
    min-height: 22px;
    color: #E5EAF1;
    selection-background-color: #2f5a8f;
}
QComboBox:hover, QDoubleSpinBox:hover, QLineEdit:hover, QSpinBox:hover {
    border-color: #69A9F5;
}
QComboBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QSpinBox:focus {
    border-color: #69A9F5;
    background-color: #2e3540;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #2B313A;
    border: 1px solid #4B5665;
    selection-background-color: #2f5a8f;
    color: #E5EAF1;
    outline: none;
}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button {
    background: #3B434E; border: none; width: 16px;
}
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover { background: #4B5665; }

/* ---- Butonlar ---- */
QPushButton {
    background-color: #3B434E;
    color: #E5EAF1;
    border: 1px solid #4B5665;
    border-radius: 6px;
    padding: 6px 16px;
    min-height: 24px;
    font-weight: 600;
    font-size: 10.5pt;
}
QPushButton:hover { background-color: #434c58; border-color: #69A9F5; }
QPushButton:pressed { background-color: #2e3540; }
QPushButton:disabled { background-color: #2f3540; color: #6f7987; border-color: #3b434e; }

QPushButton#btn_run {
    background-color: #45B881; border-color: #45B881; color: #0f2419;
}
QPushButton#btn_run:hover { background-color: #54c78f; }
QPushButton#btn_run:pressed { background-color: #3aa572; }

QPushButton#btn_stop {
    background-color: #E56B70; border-color: #E56B70; color: #2b0f10;
}
QPushButton#btn_stop:hover { background-color: #ea7d82; }
QPushButton#btn_stop:pressed { background-color: #d55b60; }

QPushButton#btn_single, QPushButton#btn_arm {
    background-color: #33587e; border-color: #456a99;
}
QPushButton#btn_single:hover, QPushButton#btn_arm:hover {
    background-color: #3c6490; border-color: #69A9F5;
}

QPushButton#btn_danger {
    background-color: #3a3440; border-color: #6e4450; color: #E56B70;
}
QPushButton#btn_danger:hover { background-color: #463a46; border-color: #E56B70; }

/* ---- Log ---- */
QPlainTextEdit, QTextEdit {
    background-color: #2B313A;
    border: 1px solid #4B5665;
    border-radius: 6px;
    color: #E5EAF1;
    font-family: "Consolas";
    font-size: 10pt;
    padding: 5px;
}

/* ---- Diğer ---- */
QCheckBox { spacing: 6px; color: #B4BECC; font-size: 10.5pt; }
QCheckBox::indicator {
    width: 15px; height: 15px;
    border: 1px solid #4B5665;
    border-radius: 4px;
    background: #2B313A;
}
QCheckBox::indicator:checked { background: #69A9F5; border-color: #69A9F5; }
QLabel { background: transparent; font-size: 10.5pt; }
QSplitter::handle { background: #2B3038; }
QScrollBar:vertical { background: #2B3038; width: 10px; border: none; }
QScrollBar::handle:vertical { background: #4B5665; border-radius: 5px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: #69A9F5; }
QScrollBar:horizontal { background: #2B3038; height: 10px; border: none; }
QScrollBar::handle:horizontal { background: #4B5665; border-radius: 5px; min-height: 20px; }

QToolTip {
    background-color: #343B45;
    color: #E5EAF1;
    border: 1px solid #4B5665;
    padding: 4px;
}
"""
