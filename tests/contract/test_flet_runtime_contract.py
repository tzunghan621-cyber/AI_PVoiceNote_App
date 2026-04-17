"""Flet 0.84 runtime contract tests — 守護框架假設不被升版打破。

T-F1: page.run_task 回傳 concurrent.futures.Future（非 asyncio.Task）
T-F2: SummaryPanel.update_highlights pre-mount 不 raise
T-F3: ActionsPanel.set_items pre-mount 不 raise
T-F4: TranscriptPanel.append pre-mount 不 raise
T-F8: BaseControl.page 未 mount 時 raise RuntimeError（contract 守護）
T-F10: ft.FilePicker() 只能在 main.py 單例建立（Bug #18：Service 不是 Control，
       不可 overlay.append；每次 on_click 新建亦會 leak 並導致 invoke_method timeout）
T-F11: FilePicker on_click handler 必須包 try/except，保證異常不 propagate
       導致 review 畫面「卡死」（Bug #18 Step 3）

參考：flet_0.84_async_lifecycle_20260417.md §1 + §7.2
       bug_report_flet_api_20260406.md §Bug #17/#18
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


# ─── T-F10 (rev): FilePicker 只能在 main.py 單例建立 (L4a 框架服務使用契約) ───

class TestFilePickerSharedInstanceContract:
    """T-F10（Bug #18 後修正版）：Flet 0.84 `ft.FilePicker` 繼承 `Service`，
    `init()` 時會透過 `context.page._services.register_service(self)` 自動
    註冊到 ServiceRegistry。兩條鐵律：

    1. **不可掛 overlay**：overlay 是 UI Control 樹，Service 不是 Control；
       混掛會讓 client 端 service listener 綁不到 →
       `RuntimeError: TimeoutException waiting for invoke method listener`。
       （Bug #18 evidence log：FilePicker ID 1076, 1077 每次 on_click 累加
       即是洩漏證據 — 每次 new instance 都新增一筆 service registration。）

    2. **不可在 handler 內 new**：ServiceRegistry.unregister_services() 會依
       refcount GC 掉「沒人長期持有」的 service。on_click 內 new 的 picker
       可能在下次 update 週期被 unregister，再次呼叫就炸。

    **正解**：`main(page)` 內建立**一顆**共用 `ft.FilePicker()`，維持 module
    區域強引用，透過 constructor 注入需要它的 view。

    Bug #17（第一次發現）修法（overlay.append）在 V Phase 第七輪實機仍炸 →
    Bug #18 定調：overlay 路徑是誤判，必須走 shared instance。

    歷史教訓：T-F10 舊版只 grep `overlay.append` 存在，**test 綠燈但實機炸** —
    這是典型 L4a gap（驗「形狀對」沒驗「真的 work」）。新版直接禁止 handler
    內建立，並要求 main.py 持有單例。
    """

    APP_DIR = pathlib.Path(__file__).resolve().parents[2] / "app"
    MAIN_PY = APP_DIR / "main.py"

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

    def test_main_py_creates_single_shared_filepicker(self):
        """main.py 必須持有一顆共用 FilePicker（module-level 或 main() 內）。"""
        text = self.MAIN_PY.read_text(encoding="utf-8")
        assert "ft.FilePicker()" in text, (
            "main.py 未建立共用 FilePicker — Bug #18 修法要求 main() 預建 "
            "`file_picker = ft.FilePicker()` 並注入 DashboardView / TermsView。"
        )

    def test_only_main_py_instantiates_filepicker(self):
        """其他檔案不可 new FilePicker；必須用 main.py 注入的共用實例。

        Bug #18 教訓：on_click 內 `ft.FilePicker()` 會 leak + 觸發 GC 風險，
        一律走 constructor 注入的 `self.file_picker.save_file(...)` 路徑。
        """
        violations = []
        for path in self.APP_DIR.rglob("*.py"):
            if path.name == "main.py":
                continue
            text = path.read_text(encoding="utf-8")
            if "ft.FilePicker()" in text:
                violations.append(str(path.relative_to(self.APP_DIR)))
        assert not violations, (
            "Bug #18 regression — 下列檔案在 main.py 以外建立 `ft.FilePicker()`：\n"
            "  - " + "\n  - ".join(violations)
            + "\n\n改用 main() 預建的共用 picker + constructor 注入："
              "\n  # main.py:   file_picker = ft.FilePicker(); MyView(..., file_picker=file_picker)"
              "\n  # view.py:   await self.file_picker.save_file(...)"
        )


# ─── T-F11: FilePicker 使用站必須包 try/except（Bug #18 Step 3）───

class TestFilePickerHandlerErrorContainment:
    """T-F11：呼叫 `self.file_picker.save_file / pick_files` 的 async on_click
    handler 必須把呼叫包在 try/except 裡，因為 Flet 0.84 任何 invoke_method
    異常（timeout / session closed / 使用者 race 取消）會原樣冒出 on_click：

        ERROR:flet:Unhandled error in 'on_click' handler
        RuntimeError: TimeoutException ...

    異常冒出後，Flet 雖然 log 但不再 dispatch 後續 update —
    → 甲方看到「review 畫面按了沒反應，只有刪除鍵有效」（Bug #18 實機症狀）。

    修法：在 picker call 外圈包 try/except，異常走 SnackBar，handler 正常 return，
    讓 Flet event loop 回到健康狀態。此 test 以 AST 掃描確保每個 picker 呼叫
    都被 try 包住（smoke-style，不跑真 Flet session — 那需 E2E，非 contract 層）。
    """

    APP_DIR = pathlib.Path(__file__).resolve().parents[2] / "app"

    def test_every_picker_call_is_wrapped_in_try(self):
        """所有 `self.file_picker.save_file` / `pick_files` 呼叫必須在 try 區塊內。"""
        import ast

        class PickerCallVisitor(ast.NodeVisitor):
            def __init__(self):
                self.violations: list[str] = []
                self._try_depth = 0
                self._func_stack: list[str] = []

            def visit_FunctionDef(self, node):
                self._func_stack.append(node.name)
                self.generic_visit(node)
                self._func_stack.pop()

            def visit_AsyncFunctionDef(self, node):
                self.visit_FunctionDef(node)

            def visit_Try(self, node):
                self._try_depth += 1
                self.generic_visit(node)
                self._try_depth -= 1

            def visit_Await(self, node):
                call = node.value
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr in ("save_file", "pick_files")
                    and isinstance(call.func.value, ast.Attribute)
                    and call.func.value.attr == "file_picker"
                ):
                    if self._try_depth == 0:
                        self.violations.append(
                            f"{self._func_stack[-1] if self._func_stack else '<module>'}"
                            f" → await self.file_picker.{call.func.attr}(...)"
                        )
                self.generic_visit(node)

        all_violations: list[str] = []
        for path in self.APP_DIR.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "file_picker." not in text:
                continue
            tree = ast.parse(text)
            v = PickerCallVisitor()
            v.visit(tree)
            for vio in v.violations:
                all_violations.append(f"{path.name}: {vio}")

        assert not all_violations, (
            "Bug #18 Step 3 regression — 下列 FilePicker 呼叫未包 try/except：\n"
            "  - " + "\n  - ".join(all_violations)
            + "\n\n異常會 propagate 到 on_click，讓 Flet log 'Unhandled error' "
              "並讓後續 update 停擺（甲方回報：畫面看似卡死，只有刪除鍵有效）。"
        )


# ─── T-F11 bonus: main.py FilePicker 注入完整性 ───

class TestFilePickerInjectionIntegrity:
    """main() 建的共用 picker 必須實際注入到所有需要它的 view。"""

    APP_DIR = pathlib.Path(__file__).resolve().parents[2] / "app"

    def test_dashboard_view_accepts_file_picker(self):
        text = (self.APP_DIR / "ui" / "dashboard_view.py").read_text(encoding="utf-8")
        assert "file_picker" in text, "DashboardView 未接受 file_picker 參數"
        assert "self.file_picker" in text, "DashboardView 未保存 file_picker 為屬性"

    def test_terms_view_accepts_file_picker(self):
        text = (self.APP_DIR / "ui" / "terms_view.py").read_text(encoding="utf-8")
        assert "file_picker" in text, "TermsView 未接受 file_picker 參數"

    def test_main_injects_file_picker_into_views(self):
        text = (self.APP_DIR / "main.py").read_text(encoding="utf-8")
        assert "file_picker=file_picker" in text, (
            "main.py 建了 file_picker 卻沒注入 view — 等同沒修。"
        )
