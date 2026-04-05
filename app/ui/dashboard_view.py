"""即時儀表板（會中）+ 編輯工作區（會後）— ui_spec#2"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Callable

import flet as ft

from app.core.models import (
    CorrectedSegment, SummaryResult, ActionItem, Participant,
    UserEdits, FeedbackEntry, Session,
)
from app.ui.main_view import (
    COLOR_BG, COLOR_SURFACE, COLOR_NAV, COLOR_TEXT, COLOR_TEXT_DIM,
    COLOR_ACCENT, COLOR_AMBER, COLOR_GREEN, COLOR_RED,
)

COLOR_AI_DIM = "#585b70"    # AI 原文灰色
COLOR_USER_BRIGHT = "#cdd6f4"  # 使用者編輯白色


# ═══════════════════════════════════════════════════════════
# 子面板元件
# ═══════════════════════════════════════════════════════════

class TranscriptPanel(ft.Container):
    """逐字稿面板 — 會中唯讀即時滾動 / 會後可標記校正回饋"""

    def __init__(self, editable: bool = False):
        self._editable = editable
        self._auto_scroll = True
        self._segments_list = ft.ListView(expand=True, spacing=2, auto_scroll=True)
        self._feedback_entries: list[FeedbackEntry] = []

        back_to_latest = ft.TextButton(
            "▼ 回到最新", on_click=lambda _: self._scroll_to_bottom(),
            visible=False,
        )
        self._back_btn = back_to_latest

        super().__init__(
            content=ft.Column([
                ft.Row([
                    ft.Text("📜 逐字稿", size=14, weight=ft.FontWeight.BOLD, color=COLOR_TEXT),
                    ft.Container(expand=True),
                    back_to_latest,
                ]),
                ft.Divider(height=1, color=COLOR_SURFACE),
                self._segments_list,
            ], expand=True, spacing=4),
            bgcolor=COLOR_BG,
            padding=10,
            expand=True,
        )

    def append(self, segment: CorrectedSegment):
        timestamp = self._format_time(segment.start)
        text_parts = [ft.Text(f"[{timestamp}] ", size=12, color=COLOR_TEXT_DIM)]

        if segment.corrections:
            # 有校正：顯示校正標記
            text_parts.append(ft.Text(segment.corrected_text, size=13, color=COLOR_TEXT))
            for c in segment.corrections:
                correction_chip = ft.Container(
                    content=ft.Text(
                        f"⚡{c.original}→{c.corrected}",
                        size=11, color=COLOR_AMBER,
                    ),
                    bgcolor="#3d2e1a",
                    border_radius=4,
                    padding=ft.padding.symmetric(horizontal=6, vertical=2),
                    tooltip=f"校正：{c.original} → {c.corrected}（{c.term_id}）",
                )
                if self._editable:
                    # 會後模式：加回饋按鈕
                    feedback_row = ft.Row([
                        correction_chip,
                        ft.IconButton(ft.Icons.CHECK, icon_size=14, icon_color=COLOR_GREEN,
                                      tooltip="正確",
                                      data={"seg": segment.index, "corr_idx": segment.corrections.index(c),
                                            "type": "correct", "term_id": c.term_id},
                                      on_click=self._on_feedback),
                        ft.IconButton(ft.Icons.CLOSE, icon_size=14, icon_color=COLOR_RED,
                                      tooltip="錯誤",
                                      data={"seg": segment.index, "corr_idx": segment.corrections.index(c),
                                            "type": "wrong", "term_id": c.term_id},
                                      on_click=self._on_feedback),
                    ], spacing=4)
                    text_parts.append(feedback_row)
                else:
                    text_parts.append(correction_chip)
        else:
            text_parts.append(ft.Text(segment.corrected_text, size=13, color=COLOR_TEXT))

        row = ft.Container(
            content=ft.Column(text_parts, spacing=2),
            padding=ft.padding.symmetric(horizontal=4, vertical=3),
        )
        self._segments_list.controls.append(row)
        if self._auto_scroll:
            self._segments_list.update()

    def _on_feedback(self, e):
        data = e.control.data
        self._feedback_entries.append(FeedbackEntry(
            segment_index=data["seg"],
            correction_index=data["corr_idx"],
            type=data["type"],
            term_id=data.get("term_id"),
            timestamp=datetime.now().isoformat(),
        ))
        e.control.icon_color = COLOR_TEXT_DIM
        e.control.disabled = True
        e.control.update()

    def get_feedback_entries(self) -> list[FeedbackEntry]:
        return list(self._feedback_entries)

    def _scroll_to_bottom(self):
        self._auto_scroll = True
        self._segments_list.auto_scroll = True
        self._segments_list.update()

    def _format_time(self, seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"


class SummaryPanel(ft.Container):
    """會議重點 + 決議事項面板 — ui_spec#2.3 / 2.4"""

    def __init__(self, editable: bool = False):
        self._editable = editable
        self._user_edited_highlights = False
        self._user_edited_decisions = False

        self._highlights_field = ft.TextField(
            multiline=True, min_lines=5, max_lines=20,
            read_only=not editable,
            border_color=COLOR_SURFACE,
            color=COLOR_AI_DIM if not editable else COLOR_TEXT,
            hint_text="會議重點將在此顯示...",
            on_change=self._on_highlights_changed if editable else None,
        )
        self._decisions_list = ft.Column(spacing=4)

        super().__init__(
            content=ft.Column([
                ft.Text("💡 會議重點", size=14, weight=ft.FontWeight.BOLD, color=COLOR_TEXT),
                ft.Divider(height=1, color=COLOR_SURFACE),
                self._highlights_field,
                ft.Container(height=10),
                ft.Text("📋 決議事項", size=14, weight=ft.FontWeight.BOLD, color=COLOR_TEXT),
                ft.Divider(height=1, color=COLOR_SURFACE),
                self._decisions_list,
            ], expand=True, spacing=4, scroll=ft.ScrollMode.AUTO),
            bgcolor=COLOR_BG,
            padding=10,
            expand=True,
        )

    def _on_highlights_changed(self, e):
        self._user_edited_highlights = True
        self._highlights_field.color = COLOR_USER_BRIGHT
        self._highlights_field.update()

    def update_highlights(self, text: str):
        if not self._user_edited_highlights:
            self._highlights_field.value = text
            self._highlights_field.color = COLOR_AI_DIM
            self._highlights_field.update()

    def update_decisions(self, decisions: list[str]):
        if not self._user_edited_decisions:
            self._decisions_list.controls.clear()
            for d in decisions:
                self._decisions_list.controls.append(
                    ft.Text(f"· {d}", size=13, color=COLOR_AI_DIM)
                )
            self._decisions_list.update()

    def get_user_edits(self) -> tuple[str | None, list[str] | None]:
        highlights = self._highlights_field.value if self._user_edited_highlights else None
        decisions = None
        if self._user_edited_decisions:
            decisions = [c.value for c in self._decisions_list.controls
                         if hasattr(c, 'value') and c.value]
        return highlights, decisions


class ActionsPanel(ft.Container):
    """Action Items 面板 — ui_spec#2.3 / 2.4"""

    def __init__(self, editable: bool = False):
        self._editable = editable
        self._items: list[ActionItem] = []
        self._items_list = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

        controls = [
            ft.Row([
                ft.Text("✅ Action Items", size=14, weight=ft.FontWeight.BOLD, color=COLOR_TEXT),
                ft.Container(expand=True),
                ft.IconButton(
                    ft.Icons.ADD_CIRCLE_OUTLINE, icon_color=COLOR_ACCENT, tooltip="新增項目",
                    on_click=self._on_add_item,
                    visible=editable,
                ),
            ]),
            ft.Divider(height=1, color=COLOR_SURFACE),
            self._items_list,
        ]

        super().__init__(
            content=ft.Column(controls, expand=True, spacing=4),
            bgcolor=COLOR_BG,
            padding=10,
            expand=True,
        )

    def merge_with_protection(self, new_actions: list[ActionItem]):
        """M-4: user_edited=True 的項目不被覆蓋"""
        existing_ids = {item.id: item for item in self._items}
        for new_item in new_actions:
            if new_item.id in existing_ids:
                if not existing_ids[new_item.id].user_edited:
                    idx = next(i for i, it in enumerate(self._items) if it.id == new_item.id)
                    self._items[idx] = new_item
            else:
                new_item.user_edited = False
                self._items.append(new_item)
        self._refresh_ui()

    def set_items(self, items: list[ActionItem]):
        self._items = list(items)
        self._refresh_ui()

    def get_items(self) -> list[ActionItem]:
        return list(self._items)

    def _refresh_ui(self):
        self._items_list.controls.clear()
        for item in self._items:
            self._items_list.controls.append(self._build_item_row(item))
        self._items_list.update()

    def _build_item_row(self, item: ActionItem) -> ft.Container:
        checkbox = ft.Checkbox(
            value=(item.status == "done"),
            on_change=lambda e, it=item: self._toggle_done(it, e),
        )
        content_text = ft.Text(
            item.content, size=13,
            color=COLOR_USER_BRIGHT if item.user_edited else COLOR_TEXT,
            weight=ft.FontWeight.BOLD if item.priority == "high" else None,
        )
        detail_parts = []
        if item.owner:
            detail_parts.append(item.owner)
        if item.deadline:
            detail_parts.append(f"期限: {item.deadline}")
        detail = ft.Text(
            " — ".join(detail_parts) if detail_parts else "",
            size=11, color=COLOR_TEXT_DIM,
        )
        priority_color = {"high": COLOR_RED, "medium": COLOR_AMBER, "low": COLOR_TEXT_DIM}
        priority_chip = ft.Container(
            content=ft.Text(item.priority, size=10, color=priority_color.get(item.priority, COLOR_TEXT_DIM)),
            bgcolor=COLOR_SURFACE,
            border_radius=4,
            padding=ft.padding.symmetric(horizontal=6, vertical=1),
        )

        row_controls = [checkbox, ft.Column([content_text, detail], spacing=1, expand=True), priority_chip]

        if self._editable:
            row_controls.append(ft.IconButton(
                ft.Icons.EDIT_OUTLINED, icon_size=16, icon_color=COLOR_TEXT_DIM,
                tooltip="編輯", on_click=lambda _, it=item: self._on_edit_item(it),
            ))

        return ft.Container(
            content=ft.Row(row_controls, vertical_alignment=ft.CrossAxisAlignment.START),
            bgcolor=COLOR_SURFACE if item.user_edited else None,
            border_radius=6,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
        )

    def _toggle_done(self, item: ActionItem, e):
        item.status = "done" if e.control.value else "open"
        item.user_edited = True
        item.updated = datetime.now().isoformat()

    def _on_add_item(self, e):
        from uuid import uuid4
        new_item = ActionItem(
            id=str(uuid4()), content="新待辦事項", owner=None, deadline=None,
            source_segment=0, status="open", priority="medium", note=None,
            user_edited=True,
            created=datetime.now().isoformat(), updated=datetime.now().isoformat(),
        )
        self._items.append(new_item)
        self._refresh_ui()

    def _on_edit_item(self, item: ActionItem):
        item.user_edited = True
        item.updated = datetime.now().isoformat()
        # 實際的編輯對話框留待 UI 打磨階段
        self._refresh_ui()


# ═══════════════════════════════════════════════════════════
# DashboardView 主體
# ═══════════════════════════════════════════════════════════

class DashboardView(ft.Container):
    """會議頁 — idle / live / review 三態"""

    def __init__(self, page: ft.Page, config, session_manager,
                 knowledge_base=None, feedback_store=None, exporter=None,
                 on_start_recording=None, on_import_audio=None, on_stop_recording=None):
        self.page = page
        self.config = config
        self.session_mgr = session_manager
        self.kb = knowledge_base
        self.feedback_store = feedback_store
        self.exporter = exporter
        self._on_start_recording = on_start_recording
        self._on_import_audio = on_import_audio
        self._on_stop_recording = on_stop_recording

        self._mode = "idle"
        self._session: Session | None = None
        self._recording_start: datetime | None = None
        self._timer_running = False  # [M-2] 計時器控制旗標

        # 面板
        self.transcript_panel: TranscriptPanel | None = None
        self.summary_panel: SummaryPanel | None = None
        self.actions_panel: ActionsPanel | None = None

        # 頂部列
        self._top_bar: ft.Container | None = None
        self._bottom_bar: ft.Container | None = None  # review 模式底部操作列
        self._timer_text: ft.Text | None = None
        self._layout_container = ft.Container(expand=True)  # [M-1] 響應式佈局容器
        self._content = ft.Container(expand=True)

        # [M-1] 監聽視窗大小變化
        page.on_resized = self._on_page_resized

        super().__init__(content=self._content, expand=True, bgcolor=COLOR_BG)
        self._build_idle()

    # ── 狀態切換 ──

    def set_mode(self, mode: str, session: Session | None = None):
        # [M-2] 離開 live 時停止計時器
        if self._mode == "live" and mode != "live":
            self._stop_timer()
        self._mode = mode
        self._session = session
        if mode == "idle":
            self._build_idle()
        elif mode == "live":
            self._build_live()
        elif mode == "review":
            self._build_review()
        self._content.update()

    # ── idle 狀態（ui_spec#2.1）──

    def _build_idle(self):
        # 歷史清單
        history = self._build_history_list()

        self._content.content = ft.Column([
            ft.Container(height=40),
            ft.Row(
                [
                    ft.ElevatedButton(
                        "🎙️ 開始錄音", color=COLOR_TEXT, bgcolor=COLOR_ACCENT,
                        on_click=self._handle_start_recording,
                        height=48, width=180,
                    ),
                    ft.Container(width=20),
                    ft.OutlinedButton(
                        "📁 匯入音檔", color=COLOR_TEXT,
                        on_click=self._handle_import_audio,
                        height=48, width=180,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            ft.Container(height=30),
            ft.Divider(color=COLOR_SURFACE),
            ft.Text("歷史紀錄", size=14, color=COLOR_TEXT_DIM,
                     weight=ft.FontWeight.BOLD),
            history,
        ], expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _build_history_list(self) -> ft.ListView:
        lv = ft.ListView(expand=True, spacing=4)
        try:
            sessions = self.session_mgr.list_sessions()
            for s in reversed(sessions):
                status_icon = {"recording": "🔴", "processing": "⏳",
                               "ready": "📋", "exported": "✅"}.get(s["status"], "📋")
                lv.controls.append(ft.ListTile(
                    leading=ft.Text(status_icon, size=16),
                    title=ft.Text(s["title"], size=13, color=COLOR_TEXT),
                    subtitle=ft.Text(f"{s['created'][:16]} — {s['status']}",
                                     size=11, color=COLOR_TEXT_DIM),
                    on_click=lambda _, sid=s["id"]: self._open_session(sid),
                ))
        except Exception:
            pass
        return lv

    def _open_session(self, session_id: str):
        session = self.session_mgr.load(session_id)
        if session:
            self.set_mode("review", session)

    # ── 會議資訊對話框（ui_spec#2.2）──

    def _show_meeting_info_dialog(self, on_confirm, on_skip):
        title_field = ft.TextField(
            label="會議名稱",
            value=f"{datetime.now():%Y-%m-%d %H:%M} 會議",
            border_color=COLOR_SURFACE,
        )
        participants_field = ft.TextField(
            label="與會人員（逗號分隔）",
            hint_text="John, Mary, ...",
            border_color=COLOR_SURFACE,
        )

        def _on_start(e):
            names = [n.strip() for n in participants_field.value.split(",") if n.strip()]
            participants = [Participant(name=n, source="manual") for n in names]
            dialog.open = False
            self.page.update()
            on_confirm(title_field.value, participants)

        def _on_skip(e):
            dialog.open = False
            self.page.update()
            on_skip()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("會議資訊（可稍後修改）"),
            content=ft.Column([title_field, participants_field], tight=True, spacing=10),
            actions=[
                ft.TextButton("跳過", on_click=_on_skip),
                ft.ElevatedButton("開始", on_click=_on_start),
            ],
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def _handle_start_recording(self, e):
        self._show_meeting_info_dialog(
            on_confirm=lambda title, parts: self._start(title, parts, "microphone"),
            on_skip=lambda: self._start(None, [], "microphone"),
        )

    def _handle_import_audio(self, e):
        def on_result(result: ft.FilePickerResultEvent):
            if result.files:
                path = result.files[0].path
                self._show_meeting_info_dialog(
                    on_confirm=lambda title, parts: self._start(title, parts, "import", path),
                    on_skip=lambda: self._start(None, [], "import", path),
                )

        picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.pick_files(
            dialog_title="選擇音檔",
            allowed_extensions=["wav", "mp3", "m4a"],
        )

    def _start(self, title, participants, source, file_path=None):
        self._recording_start = datetime.now()
        if source == "microphone" and self._on_start_recording:
            self._on_start_recording(title, participants)
        elif source == "import" and self._on_import_audio:
            self._on_import_audio(title, participants, file_path)

    # ── live 儀表板（ui_spec#2.3）──

    def _build_live(self):
        self.transcript_panel = TranscriptPanel(editable=False)
        self.summary_panel = SummaryPanel(editable=True)
        self.actions_panel = ActionsPanel(editable=True)

        # 頂部列
        self._timer_text = ft.Text("00:00:00", size=14, color=COLOR_TEXT,
                                    weight=ft.FontWeight.BOLD)
        title_text = ft.Text(
            self._session.title if self._session else "會議",
            size=13, color=COLOR_TEXT,
        )
        participants_text = ft.Text(
            self._format_participants(),
            size=11, color=COLOR_TEXT_DIM,
        )

        self._top_bar = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Text("🔴", size=16),
                    animate=ft.Animation(1000, ft.AnimationCurve.EASE_IN_OUT),
                ),
                ft.Text("錄音中", size=12, color=COLOR_RED),
                self._timer_text,
                ft.Container(width=15),
                title_text,
                ft.Container(width=10),
                ft.Text("👥", size=12),
                participants_text,
                ft.Container(expand=True),
                ft.ElevatedButton(
                    "⏹ 停止錄音", bgcolor=COLOR_RED, color=COLOR_TEXT,
                    on_click=self._handle_stop,
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
            bgcolor=COLOR_NAV,
            padding=ft.padding.symmetric(horizontal=15, vertical=8),
        )

        self._bottom_bar = None

        # [M-1] 響應式佈局
        self._layout_container = ft.Container(expand=True)
        self._apply_responsive_layout()

        self._content.content = ft.Column([
            self._top_bar,
            self._layout_container,
        ], expand=True, spacing=0)

        # [M-2] 啟動計時器
        self._start_timer()

    def _handle_stop(self, e):
        if self._on_stop_recording:
            self._on_stop_recording()

    # ── review 會後編輯（ui_spec#2.4）──

    def _build_review(self):
        self.transcript_panel = TranscriptPanel(editable=True)
        self.summary_panel = SummaryPanel(editable=True)
        self.actions_panel = ActionsPanel(editable=True)

        if self._session:
            # 填充已有資料
            for seg in self._session.segments:
                self.transcript_panel.append(seg)
            if self._session.summary:
                self.summary_panel.update_highlights(self._session.summary.highlights)
                self.summary_panel.update_decisions(self._session.summary.decisions)
                self.actions_panel.set_items(self._session.summary.action_items)
            if self._session.user_edits:
                if self._session.user_edits.highlights_edited:
                    self.summary_panel._highlights_field.value = self._session.user_edits.highlights_edited
                    self.summary_panel._user_edited_highlights = True

        # 頂部列
        duration_str = self._format_duration(self._session.audio_duration if self._session else 0)
        self._top_bar = ft.Container(
            content=ft.Row([
                ft.Text("✅ 會議結束", size=14, color=COLOR_GREEN, weight=ft.FontWeight.BOLD),
                ft.Text(duration_str, size=13, color=COLOR_TEXT_DIM),
                ft.Container(width=10),
                ft.Text(self._session.title if self._session else "", size=13, color=COLOR_TEXT),
            ], spacing=10),
            bgcolor=COLOR_NAV,
            padding=ft.padding.symmetric(horizontal=15, vertical=8),
        )

        # 底部操作
        self._bottom_bar = ft.Container(
            content=ft.Row([
                ft.ElevatedButton("匯出 Markdown", icon=ft.Icons.DOWNLOAD,
                                  on_click=self._handle_export, bgcolor=COLOR_ACCENT, color=COLOR_TEXT),
                ft.OutlinedButton("提交回饋", icon=ft.Icons.FEEDBACK,
                                  on_click=self._handle_submit_feedback),
                ft.Container(expand=True),
                ft.OutlinedButton("刪除", icon=ft.Icons.DELETE, icon_color=COLOR_RED,
                                  on_click=self._handle_delete),
            ], spacing=10),
            bgcolor=COLOR_NAV,
            padding=ft.padding.symmetric(horizontal=15, vertical=8),
        )

        # [M-1] 響應式佈局
        self._layout_container = ft.Container(expand=True)
        self._apply_responsive_layout()

        self._content.content = ft.Column([
            self._top_bar,
            self._layout_container,
            self._bottom_bar,
        ], expand=True, spacing=0)

    # ── StreamProcessor 回呼 ──

    def on_new_segment(self, segment: CorrectedSegment):
        if self.transcript_panel:
            self.transcript_panel.append(segment)

    def on_new_summary(self, summary: SummaryResult):
        if self.summary_panel:
            self.summary_panel.update_highlights(summary.highlights)
            self.summary_panel.update_decisions(summary.decisions)
        if self.actions_panel:
            self.actions_panel.merge_with_protection(summary.action_items)

    # ── [M-1] 響應式佈局 ──

    def _on_page_resized(self, e):
        """監聽視窗大小變化，重新套用佈局"""
        if self._mode in ("live", "review") and self.transcript_panel:
            self._apply_responsive_layout()
            self._layout_container.update()

    def _apply_responsive_layout(self):
        """依視窗寬度套用三段式斷點佈局（ui_spec#2.3）"""
        width = self.page.window.width if self.page and self.page.window else 1400

        if width >= 1400:
            # 寬視窗：三欄並排
            self._layout_container.content = ft.Row([
                ft.Container(content=self.transcript_panel, expand=1),
                ft.VerticalDivider(width=1, color=COLOR_SURFACE),
                ft.Container(content=self.summary_panel, expand=1),
                ft.VerticalDivider(width=1, color=COLOR_SURFACE),
                ft.Container(content=self.actions_panel, expand=1),
            ], expand=True, spacing=0)

        elif width >= 960:
            # 中等視窗：逐字稿 + 右側分頁（重點/Actions）
            right_tabs = ft.Tabs(
                selected_index=0,
                tabs=[
                    ft.Tab(text="💡 重點", content=self.summary_panel),
                    ft.Tab(text="✅ Actions", content=self.actions_panel),
                ],
                expand=True,
            )
            self._layout_container.content = ft.Row([
                ft.Container(content=self.transcript_panel, expand=1),
                ft.VerticalDivider(width=1, color=COLOR_SURFACE),
                ft.Container(content=right_tabs, expand=1),
            ], expand=True, spacing=0)

        else:
            # 窄視窗：單欄分頁
            self._layout_container.content = ft.Tabs(
                selected_index=0,
                tabs=[
                    ft.Tab(text="📜 逐字稿", content=self.transcript_panel),
                    ft.Tab(text="💡 重點", content=self.summary_panel),
                    ft.Tab(text="✅ Actions", content=self.actions_panel),
                ],
                expand=True,
            )

    # ── [M-2] 會中計時器 ──

    def _start_timer(self):
        """開始錄音時啟動計時器，每秒更新"""
        self._timer_running = True

        async def _update_timer():
            while self._timer_running and self._recording_start:
                elapsed = (datetime.now() - self._recording_start).total_seconds()
                if self._timer_text:
                    self._timer_text.value = self._format_duration(elapsed)
                    try:
                        self._timer_text.update()
                    except Exception:
                        break
                await asyncio.sleep(1)

        self.page.run_task(_update_timer)

    def _stop_timer(self):
        """停止計時器"""
        self._timer_running = False

    # ── 底部操作 ──

    def _handle_export(self, e):
        if not self._session or not self.exporter:
            return

        def on_result(result: ft.FilePickerResultEvent):
            if result.path:
                self._save_user_edits()
                self.exporter.export(self._session, result.path)
                self.session_mgr.save(self._session)
                # 匯出後詢問是否刪除音檔（ui_spec#7）
                self._show_delete_audio_dialog()

        picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.save_file(
            dialog_title="匯出 Markdown",
            file_name=f"{self._session.title}.md",
            allowed_extensions=["md"],
        )

    def _show_delete_audio_dialog(self):
        def _delete(e):
            self.session_mgr.delete_audio(self._session)
            self.session_mgr.save(self._session)
            dlg.open = False
            self.page.update()

        def _keep(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("匯出完成"),
            content=ft.Text("是否刪除原始音檔？"),
            actions=[
                ft.TextButton("保留", on_click=_keep),
                ft.ElevatedButton("刪除", on_click=_delete, bgcolor=COLOR_RED, color=COLOR_TEXT),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _handle_submit_feedback(self, e):
        if not self._session or not self.feedback_store:
            return
        from app.core.models import SessionFeedback
        entries = self.transcript_panel.get_feedback_entries() if self.transcript_panel else []
        fb = SessionFeedback(
            session_id=self._session.id,
            created=datetime.now().isoformat(),
            entries=entries,
            summary_rating=0,
        )
        self.feedback_store.save(fb)
        self._show_snackbar("回饋已提交")

    def _handle_delete(self, e):
        def _confirm(ev):
            if self._session:
                self.session_mgr.delete_audio(self._session)
                # 刪除 session JSON
                import os
                path = self.session_mgr.sessions_dir / f"{self._session.id}.json"
                if path.exists():
                    path.unlink()
            dlg.open = False
            self.page.update()
            self.set_mode("idle")

        dlg = ft.AlertDialog(
            title=ft.Text("確定刪除此會議紀錄？"),
            content=ft.Text("此操作無法復原。"),
            actions=[
                ft.TextButton("取消", on_click=lambda e: setattr(dlg, 'open', False) or self.page.update()),
                ft.ElevatedButton("確定", on_click=_confirm, bgcolor=COLOR_RED, color=COLOR_TEXT),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _save_user_edits(self):
        if not self._session:
            return
        highlights, decisions = self.summary_panel.get_user_edits() if self.summary_panel else (None, None)
        if highlights or decisions:
            edits = UserEdits(
                highlights_edited=highlights,
                decisions_edited=decisions,
                edited_at=datetime.now().isoformat(),
            )
            self.session_mgr.save_user_edits(self._session, edits)

    def _show_snackbar(self, msg: str):
        self.page.snack_bar = ft.SnackBar(content=ft.Text(msg))
        self.page.snack_bar.open = True
        self.page.update()

    # ── 工具 ──

    def _format_participants(self) -> str:
        if not self._session or not self._session.participants:
            return ""
        names = [p.name for p in self._session.participants[:3]]
        extra = len(self._session.participants) - 3
        result = ", ".join(names)
        if extra > 0:
            result += f" +{extra}"
        return result

    def _format_duration(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
