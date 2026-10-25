# SPDX-License-Identifier: GPL-3.0-or-later
"""Choosing Paint reveals its palette, even if Properties was folded or hidden."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def window(tmp_path, monkeypatch):
    import core.extensions as extensions
    import PySide6.QtCore as qc
    import views.main_window as mw

    settings = lambda *a: QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat)
    monkeypatch.setattr(qc, "QSettings", settings)
    monkeypatch.setattr(mw, "QSettings", settings)
    monkeypatch.setattr(extensions, "plugin_dirs", lambda: [tmp_path])
    from tools.paint import PaintTool
    paint_state = {name: value for name, value in vars(PaintTool).items()
                   if name.startswith("current_")}
    win = mw.MainWindow()
    win.resize(1200, 800)
    win.show()
    win.activateWindow()
    win.viewport.setFocus()
    settle()
    yield win
    win._saved_version = win.viewport.scene.version
    win.close()
    for name, value in paint_state.items():
        setattr(PaintTool, name, value)


def settle():
    for _ in range(8):
        QApplication.processEvents()


def assert_materials_visible(win):
    section = win.tray.materials.parentWidget()
    scroll = win.tray.widget()
    assert not win.tray.isHidden()
    assert not win.tray.visibleRegion().isEmpty()
    assert section._btn.isChecked()
    assert win.tray.materials.isVisible()
    header = section._btn.mapTo(scroll.viewport(), QPoint(0, 0))
    assert 0 <= header.y() < scroll.viewport().height()
    bar = scroll.verticalScrollBar()
    assert bar.value() == min(section.y(), bar.maximum())
    assert win.viewport.active_tool is win._tools["paint"]


@pytest.mark.parametrize("entry", ["shortcut", "action", "repeat"])
def test_paint_opens_and_scrolls_to_materials(window, entry):
    win = window
    section = win.tray.materials.parentWidget()
    section._btn.setChecked(False)
    win.tray.widget().verticalScrollBar().setValue(0)
    win.project_browser.raise_()
    settle()
    if entry == "shortcut":
        assert win._tool_actions["paint"].shortcut() == QKeySequence("B")
        QTest.keyClick(win.viewport, Qt.Key_B)
    elif entry == "action":
        win._tool_actions["paint"].trigger()
    else:
        win._tool_actions["paint"].trigger()
        section._btn.setChecked(False)
        win._activate_tool("select")
        win.repeat_last_command()
    settle()
    assert_materials_visible(win)


@pytest.mark.parametrize("hidden", ["closed", "sidebar"])
def test_paint_restores_hidden_properties(window, hidden):
    win = window
    if hidden == "closed":
        win.set_tray_shown(win.tray, False)
    else:
        win._act_sidebar.setChecked(False)
    win._tool_actions["paint"].trigger()
    settle()
    assert_materials_visible(win)
    assert win._act_sidebar.isChecked()


def test_paint_keeps_viewport_focus_and_does_not_edit_model(window):
    win = window
    vp = win.viewport
    before = (vp.scene.version, len(vp.history.undo_stack), dict(vp.scene.materials))
    win.viewport.setFocus()
    win._tool_actions["paint"].trigger()
    settle()
    assert vp.hasFocus()
    assert before == (vp.scene.version, len(vp.history.undo_stack), dict(vp.scene.materials))
    # Press B again while Paint is already active: reveal the palette again.
    win.tray.materials.parentWidget()._btn.click()
    settle()
    QTest.keyClick(vp, Qt.Key_B)
    settle()
    assert_materials_visible(win)


def test_other_tools_and_unavailable_paint_leave_materials_alone(window):
    win = window
    section = win.tray.materials.parentWidget()
    section._btn.setChecked(False)
    win.tray.widget().verticalScrollBar().setValue(0)
    win._activate_tool("line")
    settle()
    assert not section._btn.isChecked()
    assert win.tray.widget().verticalScrollBar().value() == 0
    win._tool_filter = {"select", "line"}
    win._tool_actions["paint"].trigger()
    settle()
    assert win.viewport.active_tool is win._tools["line"]
    assert not section._btn.isChecked()


def test_picking_a_swatch_keeps_the_palette_scroll_position(window):
    win = window
    win._tool_actions["paint"].trigger()
    settle()
    scroll = win.tray.widget()
    bar = scroll.verticalScrollBar()
    bar.setValue(bar.maximum())
    settle()
    position = bar.value()
    assert position > win.tray.materials.parentWidget().y()
    win.tray.materials._apply_color((0.2, 0.4, 0.6))
    settle()
    assert win.viewport.active_tool is win._tools["paint"]
    assert bar.value() == position
