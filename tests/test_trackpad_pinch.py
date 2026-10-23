# SPDX-License-Identifier: GPL-3.0-or-later
"""Trackpad pinch zoom through Qt's actual input dispatch, without hardware."""
from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QNativeGestureEvent, QPointingDevice, QWheelEvent, QVector3D
from PySide6.QtWidgets import QApplication

from core.camera import MIN_DISTANCE, MAX_DISTANCE
from views.viewport import Viewport


@pytest.fixture
def vp():
    viewport = Viewport()
    viewport.resize(800, 600)
    viewport.camera.set_aspect(800, 600)
    yield viewport
    viewport.close()


def native(vp, kind, value=0.0, pos=None):
    pos = pos or QPointF(400, 300)
    ev = QNativeGestureEvent(kind, QPointingDevice.primaryPointingDevice(),
                             2, pos, pos, pos, value, QPointF())
    ev.ignore()
    QApplication.sendEvent(vp, ev)
    return ev


def wheel(vp, delta, modifiers=Qt.NoModifier):
    pos = QPointF(400, 300)
    QApplication.sendEvent(vp, QWheelEvent(
        pos, pos, QPoint(), QPoint(0, delta), Qt.NoButton,
        modifiers, Qt.NoScrollPhase, False))


@pytest.mark.parametrize("perspective", [True, False])
def test_spreading_and_pinching_scale_the_view_and_keep_the_cursor_anchor(
        vp, monkeypatch, perspective):
    vp.camera.perspective = perspective
    focus = QVector3D(3, 2, 0)
    monkeypatch.setattr(vp, "_world_under_cursor", lambda x, y: focus)
    pos = QPointF(*vp._world_to_pixel(focus))
    d0 = vp.camera.distance
    target0 = QVector3D(vp.camera.target)
    screen0 = vp._world_to_pixel(focus)
    native(vp, Qt.BeginNativeGesture)
    ev = native(vp, Qt.ZoomNativeGesture, 0.25, pos)
    assert ev.isAccepted()
    assert vp.camera.distance == pytest.approx(d0 / 1.25)
    assert vp._world_to_pixel(focus) == pytest.approx(screen0, abs=1e-4)
    native(vp, Qt.ZoomNativeGesture, -0.2, pos)
    assert vp.camera.distance == pytest.approx(d0)
    assert (vp.camera.target - target0).length() < 1e-5
    native(vp, Qt.EndNativeGesture)


def test_tiny_outward_deltas_do_not_apply_a_whole_wheel_notch_retreat(
        vp, monkeypatch):
    focus = QVector3D(vp.camera.target)
    vp.camera.distance = 0.1
    eye0 = vp.camera.eye()
    monkeypatch.setattr(vp, "_world_under_cursor", lambda x, y: focus)
    native(vp, Qt.ZoomNativeGesture, -0.001)
    assert vp.camera.distance == pytest.approx(0.1 / 0.999)
    assert (vp.camera.eye() - eye0).length() < 0.001


def test_one_pick_per_gesture_and_a_fresh_pick_after_an_edit(vp, monkeypatch):
    picks = []

    def pick(x, y):
        picks.append((x, y))
        return QVector3D(0, 0, 0)

    monkeypatch.setattr(vp, "_world_under_cursor", pick)
    native(vp, Qt.BeginNativeGesture)
    for _ in range(5):
        native(vp, Qt.ZoomNativeGesture, 0.01)
    assert len(picks) == 1
    # Do not let reprojection reuse the old focus after a document edit.
    vp.scene.version += 1
    native(vp, Qt.ZoomNativeGesture, 0.01)
    assert len(picks) == 2
    native(vp, Qt.EndNativeGesture)
    native(vp, Qt.BeginNativeGesture)
    native(vp, Qt.ZoomNativeGesture, 0.01)
    assert len(picks) == 3


def test_native_pinch_direction_is_independent_of_the_wheel_preference(vp):
    vp._invert_wheel = True
    d0 = vp.camera.distance
    native(vp, Qt.ZoomNativeGesture, 0.1)
    assert vp.camera.distance < d0


@pytest.mark.parametrize("delta", [0.0, -1.0, -2.0, math.nan, math.inf, -math.inf])
def test_invalid_or_zero_native_deltas_leave_the_camera_unchanged(vp, delta):
    before = (QVector3D(vp.camera.target), vp.camera.distance)
    native(vp, Qt.ZoomNativeGesture, delta)
    assert vp.camera.target == before[0] and vp.camera.distance == before[1]
    assert vp.camera.is_finite()


def test_empty_space_and_distance_limits_stay_usable(vp, monkeypatch):
    monkeypatch.setattr(vp, "_world_under_cursor", lambda x, y: None)
    for delta, distance in [(100.0, MIN_DISTANCE), (-0.999, MAX_DISTANCE)]:
        vp.camera.distance = distance
        native(vp, Qt.ZoomNativeGesture, delta)
        assert MIN_DISTANCE <= vp.camera.distance <= MAX_DISTANCE
        assert vp.camera.is_finite()


def test_interleaved_rotation_does_not_turn_or_zoom_the_camera(vp):
    before = (vp.camera.yaw, vp.camera.pitch, vp.camera.distance)
    native(vp, Qt.BeginNativeGesture)
    native(vp, Qt.RotateNativeGesture, 5.0)
    assert (vp.camera.yaw, vp.camera.pitch, vp.camera.distance) == before


def test_ctrl_wheel_pinch_fallback_uses_small_continuous_deltas(vp, monkeypatch):
    focus = QVector3D(vp.camera.target)
    monkeypatch.setattr(vp, "_world_under_cursor", lambda x, y: focus)
    vp.camera.distance = 0.1
    eye0 = vp.camera.eye()
    wheel(vp, -1, Qt.ControlModifier)
    assert (vp.camera.eye() - eye0).length() < 0.001
    wheel(vp, 1, Qt.ControlModifier)
    assert vp.camera.distance == pytest.approx(0.1)


def test_regular_wheel_keeps_its_direction_preference_and_close_up_retreat(vp, monkeypatch):
    monkeypatch.setattr(vp, "_world_under_cursor", lambda x, y: QVector3D(0, 0, 0))
    vp.camera.target = QVector3D(0, 0, 0)
    vp.camera.distance = MIN_DISTANCE
    vp._invert_wheel = True
    eye0 = vp.camera.eye()
    wheel(vp, 120)
    assert (vp.camera.eye() - eye0).length() >= 0.05 - 1e-6
