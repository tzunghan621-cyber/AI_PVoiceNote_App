"""Flet 0.84 runtime contract tests — 守護框架假設不被升版打破。

T-F1: page.run_task 回傳 concurrent.futures.Future（非 asyncio.Task）
T-F2: SummaryPanel.update_highlights pre-mount 不 raise
T-F3: ActionsPanel.set_items pre-mount 不 raise
T-F4: TranscriptPanel.append pre-mount 不 raise
T-F8: BaseControl.page 未 mount 時 raise RuntimeError（contract 守護）
T-F10: 所有 ft.FilePicker() 建立處必須掛 page.overlay（L4a 框架服務使用契約，Bug #17）

參考：flet_0.84_async_lifecycle_20260417.md §1 + §7.2
       bug_report_flet_api_20260406.md §Bug #17
"""

from __future__ import annotations

import concurrent.futures
import inspect
import pathlib
import re

import pytest
import flet as ft

from app.core.models import CorrectedSegment, ActionItem
from app.ui.dashboard_view import TranscriptPanel, SummaryPanel, ActionsPanel


# ─── T-F1: page.run_task 回傳 concurrent.futures.Future contract ───

class TestRunTaskReturnType:
    """T-F1：驗證 Flet 0.84 Page.run_task 使用 asyncio.run_coroutine_threadsafe（回傳 cf.Future）。

    Bug #13 根因：碼農假設 run_task 回 asyncio.Task → asyncio.shield(cf.Future) TypeError。
    此 test 透過 inspect 驗證內部仍走 run_coroutine_threadsafe bridge。
    若 Flet 升版改用 create_task 或其他方式，此 test fail → trigger researcher 重新 review。
    """

    def test_run_task_source_uses_run_coroutine_threadsafe(self):
        """run_task 內部使用 asyncio.run_coroutine_threadsafe → 回傳 cf.Future"""
        source = inspect.getsource(ft.Page.run_task)
        assert "run_coroutine_threadsafe" in source, (
            "Flet Page.run_task no longer uses asyncio.run_coroutine_threadsafe. "
            "Return type may have changed from concurrent.futures.Future — "
            "researcher needs to re-review _stop_recording_async compatibility."
        )

    def test_cf_future_has_no_await(self):
        """concurrent.futures.Future 沒有 __await__ — 確認為什麼不能 asyncio.shield 它"""
        f = concurrent.futures.Future()
        assert not hasattr(f, "__await__") or f.__await__ is None, (
            "concurrent.futures.Future gained __await__ — "
            "asyncio.shield/wait_for may now work directly. Review needed."
        )


# ─── T-F2: SummaryPanel pre-mount safety ───

class TestSummaryPanelPreMount:
    """SummaryPanel 在未 mount 時呼叫 update_highlights / update_decisions 不應 raise。"""

    def test_update_highlights_pre_mount_no_raise(self):
        panel = SummaryPanel(editable=True)
        # 未 mount → _mounted == False
        assert panel._mounted is False
        # 呼叫不應 raise
        panel.update_highlights("測試重點文字")
        # state 仍正確改變（值已寫入 field）
        assert panel._highlights_field.value == "測試重點文字"

    def test_update_decisions_pre_mount_no_raise(self):
        panel = SummaryPanel(editable=True)
        assert panel._mounted is False
        panel.update_decisions(["決議一", "決議二"])
        assert len(panel._decisions_list.controls) == 2


# ─── T-F3: ActionsPanel pre-mount safety ───

class TestActionsPanelPreMount:
    """ActionsPanel 在未 mount 時呼叫 set_items 不應 raise。"""

    def test_set_items_pre_mount_no_raise(self):
        panel = ActionsPanel(editable=True)
        assert panel._mounted is False
        items = [
            ActionItem(
                id="test-1", content="待辦事項", owner="John",
                deadline="2026-04-20", source_segment=0, status="open",
                priority="medium", note=None, user_edited=False,
                created="2026-04-17", updated="2026-04-17",
            ),
        ]
        panel.set_items(items)
        assert len(panel._items) == 1
        assert len(panel._items_list.controls) == 1

    def test_merge_with_protection_pre_mount_no_raise(self):
        panel = ActionsPanel(editable=True)
        assert panel._mounted is False
        items = [
            ActionItem(
                id="test-2", content="新待辦", owner=None,
                deadline=None, source_segment=0, status="open",
                priority="high", note=None, user_edited=False,
                created="2026-04-17", updated="2026-04-17",
            ),
        ]
        panel.merge_with_protection(items)
        assert len(panel._items) == 1


# ─── T-F4: TranscriptPanel pre-mount safety ───

class TestTranscriptPanelPreMount:
    """TranscriptPanel 在未 mount 時呼叫 append 不應 raise。"""

    def test_append_pre_mount_no_raise(self):
        panel = TranscriptPanel(editable=False)
        assert panel._mounted is False
        seg = CorrectedSegment(
            index=0, start=0.0, end=5.0,
            original_text="測試文字",
            corrected_text="測試文字",
            corrections=[],
        )
        panel.append(seg)
        assert len(panel._segments_list.controls) == 1

    def test_scroll_to_bottom_pre_mount_no_raise(self):
        panel = TranscriptPanel(editable=False)
        assert panel._mounted is False
        panel._scroll_to_bottom()


# ─── T-F8: BaseControl.page 未 mount 時 raise RuntimeError ───

class TestFletPagePropertyContract:
    """驗證 Flet 0.84 BaseControl.page 未 mount 時 raise RuntimeError。

    若此 test fail，代表 Flet 升版改了 page property 行為，
    需 trigger researcher 重新 review lifecycle 假設。
    """

    def test_page_raises_runtime_error_when_not_mounted(self):
        ctrl = ft.Container(content=ft.Text("probe"))
        with pytest.raises(RuntimeError, match="Control must be added to the page first"):
            _ = ctrl.page

    def test_page_raises_on_custom_control(self):
        panel = SummaryPanel(editable=False)
        with pytest.raises(RuntimeError):
            _ = panel.page


# ─── T-F10: FilePicker 必須掛 page.overlay (L4a 框架服務使用契約) ───

class TestFilePickerOverlayContract:
    """T-F10：Flet 0.84 `ft.FilePicker` 是 service control，
    呼叫 `save_file` / `pick_files` 時需透過 session message channel
    dispatch 到 client；picker 未 mount 在 page tree（通常是 `page.overlay`）
    會讓 `_invoke_method` 找不到 session 綁定 → `RuntimeError: Session closed`。

    Bug #17（V Phase 第七輪甲方實機匯出 Markdown 首次暴露）。

    防線：grep-based pattern test — 專案內所有 `ft.FilePicker()` 建立處
    對應函式內必定出現 `overlay.append(picker)` 呼叫。此測試屬 L4a
    （框架服務使用契約），現有 T-F1/T-F8 只驗 API 簽章 / property
    lifecycle，不驗「要怎麼用才 work」。

    若 Flet 未來版本放寬此契約（picker 可直接呼叫 save_file 而不 mount），
    仍可保留本 test — 它會持續防止「有人建 FilePicker 忘了 overlay」的
    回歸，即便當下不再炸也屬 dead pattern。
    """

    APP_DIR = pathlib.Path(__file__).resolve().parents[2] / "app"

    def _iter_filepicker_sites(self):
        """yield (file, func_name, func_text) 若 func 內建 ft.FilePicker()"""
        func_pattern = re.compile(
            r"^(\s*)(?:async\s+)?def\s+(\w+)\s*\(.*?\):\s*\n(.*?)(?=^\1(?:async\s+)?def\s+|^\1class\s+|\Z)",
            re.DOTALL | re.MULTILINE,
        )
        for path in self.APP_DIR.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "ft.FilePicker()" not in text:
                continue
            for match in func_pattern.finditer(text):
                func_name = match.group(2)
                func_text = match.group(0)
                if "ft.FilePicker()" in func_text:
                    yield path, func_name, func_text

    def test_every_filepicker_usage_mounts_to_overlay(self):
        """App 內每個 ft.FilePicker() 建立處同函式內必含 overlay.append(picker)。

        若此測試 fail：Bug #17 風格回歸出現（即 `RuntimeError: Session closed`
        潛伏），追建 picker 的函式並加 `page.overlay.append(picker)` pattern。
        """
        sites = list(self._iter_filepicker_sites())
        assert sites, (
            "Expected to find at least one `ft.FilePicker()` in app/ "
            "(dashboard export/import, terms_view import). Did they "
            "all get replaced with a different API? Update this test."
        )
        violations = []
        for path, func_name, func_text in sites:
            if "overlay.append" not in func_text:
                violations.append(f"{path.name}::{func_name}")
        assert not violations, (
            "Bug #17 regression — the following functions create "
            "`ft.FilePicker()` without mounting to `page.overlay`:\n  - "
            + "\n  - ".join(violations)
            + "\nPattern required (bug_report §Bug #17):\n"
              "  picker = ft.FilePicker()\n"
              "  self._page_ref.overlay.append(picker); self._page_ref.update()\n"
              "  try:\n      path = await picker.save_file(...)\n"
              "  finally:\n      self._page_ref.overlay.remove(picker); self._page_ref.update()"
        )

    def test_every_filepicker_usage_removes_from_overlay(self):
        """搭配 append 必須有 remove（finally 內）避免累積洩漏。"""
        for path, func_name, func_text in self._iter_filepicker_sites():
            if "overlay.append" in func_text:
                assert "overlay.remove" in func_text, (
                    f"{path.name}::{func_name} appends FilePicker to overlay "
                    f"but never removes it (should be in finally block)."
                )
