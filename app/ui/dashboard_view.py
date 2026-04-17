"""即時儀表板（會中）+ 編輯工作區（會後）— ui_spec#2"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Callable

import flet as ft

from app.core.audio_recorder import AudioRecorder
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
        self._mounted = False
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

    def did_mount(self):
        self._mounted = True

    def will_unmount(self):
        self._mounted = False

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
                    padding=ft.Padding(left=6, right=6, top=2, bottom=2),
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
            padding=ft.Padding(left=4, right=4, top=3, bottom=3),
        )
        self._segments_list.controls.append(row)
        if self._auto_scroll and self._mounted:
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
        if self._mounted:
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
        self._mounted = False
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

    def did_mount(self):
        self._mounted = True

    def will_unmount(self):
        self._mounted = False

    def _on_highlights_changed(self, e):
        self._user_edited_highlights = True
        self._highlights_field.color = COLOR_USER_BRIGHT
        if self._mounted:
            self._highlights_field.update()

    def update_highlights(self, text: str):
        if not self._user_edited_highlights:
            self._highlights_field.value = text
            self._highlights_field.color = COLOR_AI_DIM
            if self._mounted:
                self._highlights_field.update()

    def update_decisions(self, decisions: list[str]):
        if not self._user_edited_decisions:
            self._decisions_list.controls.clear()
            for d in decisions:
                self._decisions_list.controls.append(
                    ft.Text(f"· {d}", size=13, color=COLOR_AI_DIM)
                )
            if self._mounted:
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
        self._mounted = False
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

    def did_mount(self):
        self._mounted = True

    def will_unmount(self):
        self._mounted = False

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
        if self._mounted:
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
            padding=ft.Padding(left=6, right=6, top=1, bottom=1),
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
            padding=ft.Padding(left=8, right=8, top=4, bottom=4),
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
                 audio_recorder=None,
                 on_start_recording=None, on_import_audio=None, on_stop_recording=None):
        self._page_ref = page
        self.config = config
        self.session_mgr = session_manager
        self.kb = knowledge_base
        self.feedback_store = feedback_store
        self.exporter = exporter
        self._audio_recorder = audio_recorder
        self._on_start_recording = on_start_recording
        self._on_import_audio = on_import_audio
        self._on_stop_recording = on_stop_recording

        self._mode = "idle"
        self._mounted = False
        self._session: Session | None = None
        self._recording_start: datetime | None = None
        self._timer_running = False  # [M-2] 計時器控制旗標
        self._level_poll_running = False  # Mic Live 音量 poll

        # Mic Live 指示器 config
        mic_cfg = config if hasattr(config, 'get') else None
        self._mic_poll_ms = (mic_cfg.get("ui.mic_indicator.poll_interval_ms", 200) if mic_cfg else 200)
        self._mic_thresholds = {
            "silent": (mic_cfg.get("ui.mic_indicator.threshold_silent_dbfs", -40) if mic_cfg else -40),
            "normal": (mic_cfg.get("ui.mic_indicator.threshold_normal_dbfs", -30) if mic_cfg else -30),
            "loud": (mic_cfg.get("ui.mic_indicator.threshold_loud_dbfs", -12) if mic_cfg else -12),
            "clipping": (mic_cfg.get("ui.mic_indicator.threshold_clipping_dbfs", -3) if mic_cfg else -3),
        }
        self._mic_test_duration = (mic_cfg.get("ui.mic_indicator.test_duration_sec", 5) if mic_cfg else 5)

        # 面板
        self.transcript_panel: TranscriptPanel | None = None
        self.summary_panel: SummaryPanel | None = None
        self.actions_panel: ActionsPanel | None = None

        # 頂部列
        self._top_bar: ft.Container | None = None
        self._bottom_bar: ft.Container | None = None  # review 模式底部操作列
        self._timer_text: ft.Text | None = None
        self._mic_level_bar: ft.ProgressBar | None = None  # Mic Live 音量條
        self._mic_level_text: ft.Text | None = None  # dBFS 文字
        self._layout_container = ft.Container(expand=True)  # [M-1] 響應式佈局容器
        self._content = ft.Container(expand=True)

        # [M-1] 監聽視窗大小變化
        page.on_resize = self._on_page_resized

        super().__init__(content=self._content, expand=True, bgcolor=COLOR_BG)
        self._build_idle()

    def did_mount(self):
        self._mounted = True

    def will_unmount(self):
        self._mounted = False

    # ── 狀態切換 ──

    def set_mode(self, mode: str, session: Session | None = None):
        # [M-2] 離開 live 時停止計時器 + Mic Live poll
        if self._mode == "live" and mode != "live":
            self._stop_timer()
            self._stop_level_poll()
        self._mode = mode
        self._session = session
        if mode == "idle":
            self._build_idle()
        elif mode == "live":
            self._build_live()
        elif mode == "review":
            self._build_review()
        if self._mounted:
            self._content.update()

    # ── idle 狀態（ui_spec#2.1）──

    def _build_idle(self):
        # 歷史清單
        history = self._build_history_list()

        # Mic Test 區塊（預設隱藏，按按鈕時展開）
        self._mic_test_container = ft.Container(visible=False)

        self._content.content = ft.Column([
            ft.Container(height=40),
            ft.Row(
                [
                    ft.ElevatedButton(
                        "🎙️ 開始錄音",
                        style=ft.ButtonStyle(color=COLOR_TEXT, bgcolor=COLOR_ACCENT),
                        on_click=self._handle_start_recording,
                        height=48, width=180,
                    ),
                    ft.Container(width=20),
                    ft.OutlinedButton(
                        "📁 匯入音檔",
                        style=ft.ButtonStyle(color=COLOR_TEXT),
                        on_click=self._handle_import_audio,
                        height=48, width=180,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            ft.Container(height=10),
            ft.Row(
                [ft.OutlinedButton(
                    "🎤 測試麥克風",
                    style=ft.ButtonStyle(color=COLOR_TEXT_DIM),
                    on_click=self._handle_mic_test,
                    height=36,
                )],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            self._mic_test_container,
            ft.Container(height=15),
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
            self._page_ref.pop_dialog()
            on_confirm(title_field.value, participants)

        def _on_skip(e):
            self._page_ref.pop_dialog()
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
        self._page_ref.show_dialog(dialog)

    def _handle_start_recording(self, e):
        self._show_meeting_info_dialog(
            on_confirm=lambda title, parts: self._start(title, parts, "microphone"),
            on_skip=lambda: self._start(None, [], "microphone"),
        )

    async def _handle_import_audio(self, e):
        # Bug #17：同 _handle_export — FilePicker 必須先掛 page.overlay
        picker = ft.FilePicker()
        self._page_ref.overlay.append(picker)
        self._page_ref.update()
        try:
            files = await picker.pick_files(
                dialog_title="選擇音檔",
                allowed_extensions=["wav", "mp3", "m4a"],
            )
            if files:
                path = files[0].path
                self._show_meeting_info_dialog(
                    on_confirm=lambda title, parts: self._start(title, parts, "import", path),
                    on_skip=lambda: self._start(None, [], "import", path),
                )
        finally:
            if picker in self._page_ref.overlay:
                self._page_ref.overlay.remove(picker)
                self._page_ref.update()

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

        # Mic Live 音量條（ui_spec §2.5）
        self._mic_level_bar = ft.ProgressBar(
            value=0, width=100, bar_height=8,
            color=COLOR_GREEN, bgcolor=COLOR_SURFACE,
        )
        self._mic_level_text = ft.Text(
            "-80 dBFS", size=10, color=COLOR_TEXT_DIM,
        )

        self._top_bar = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Text("🔴", size=16),
                    animate=ft.Animation(1000, ft.AnimationCurve.EASE_IN_OUT),
                ),
                ft.Text("錄音中", size=12, color=COLOR_RED),
                self._timer_text,
                ft.Container(width=8),
                ft.Text("🎤", size=14),
                self._mic_level_bar,
                self._mic_level_text,
                ft.Container(width=8),
                title_text,
                ft.Container(width=10),
                ft.Text("👥", size=12),
                participants_text,
                ft.Container(expand=True),
                ft.ElevatedButton(
                    "⏹ 停止錄音",
                    style=ft.ButtonStyle(bgcolor=COLOR_RED, color=COLOR_TEXT),
                    on_click=self._handle_stop,
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
            bgcolor=COLOR_NAV,
            padding=ft.Padding(left=15, right=15, top=8, bottom=8),
        )

        self._bottom_bar = None

        # [M-1] 響應式佈局
        self._layout_container = ft.Container(expand=True)
        self._apply_responsive_layout()

        self._content.content = ft.Column([
            self._top_bar,
            self._layout_container,
        ], expand=True, spacing=0)

        # [M-2] 啟動計時器 + Mic Live poll
        self._start_timer()
        self._start_level_poll()

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
            padding=ft.Padding(left=15, right=15, top=8, bottom=8),
        )

        # 底部操作
        self._bottom_bar = ft.Container(
            content=ft.Row([
                ft.ElevatedButton("匯出 Markdown", icon=ft.Icons.DOWNLOAD,
                                  on_click=self._handle_export,
                                  style=ft.ButtonStyle(bgcolor=COLOR_ACCENT, color=COLOR_TEXT)),
                ft.OutlinedButton("提交回饋", icon=ft.Icons.FEEDBACK,
                                  on_click=self._handle_submit_feedback),
                ft.Container(expand=True),
                ft.OutlinedButton("刪除", icon=ft.Icons.DELETE,
                                  style=ft.ButtonStyle(color=COLOR_RED),
                                  on_click=self._handle_delete),
            ], spacing=10),
            bgcolor=COLOR_NAV,
            padding=ft.Padding(left=15, right=15, top=8, bottom=8),
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
            if self._mounted:
                self._layout_container.update()

    def _apply_responsive_layout(self):
        """依視窗寬度套用三段式斷點佈局（ui_spec#2.3）"""
        width = self._page_ref.window.width if self._mounted and self._page_ref.window else 1400

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
            right_tab_bar = ft.TabBar(tabs=[
                ft.Tab(label="💡 重點"),
                ft.Tab(label="✅ Actions"),
            ])
            right_tab_view = ft.TabBarView(controls=[
                self.summary_panel,
                self.actions_panel,
            ], expand=True)
            right_tabs = ft.Tabs(
                length=2,
                selected_index=0,
                content=ft.Column([right_tab_bar, right_tab_view], expand=True, spacing=0),
                expand=True,
            )
            self._layout_container.content = ft.Row([
                ft.Container(content=self.transcript_panel, expand=1),
                ft.VerticalDivider(width=1, color=COLOR_SURFACE),
                ft.Container(content=right_tabs, expand=1),
            ], expand=True, spacing=0)

        else:
            # 窄視窗：單欄分頁
            single_tab_bar = ft.TabBar(tabs=[
                ft.Tab(label="📜 逐字稿"),
                ft.Tab(label="💡 重點"),
                ft.Tab(label="✅ Actions"),
            ])
            single_tab_view = ft.TabBarView(controls=[
                self.transcript_panel,
                self.summary_panel,
                self.actions_panel,
            ], expand=True)
            self._layout_container.content = ft.Tabs(
                length=3,
                selected_index=0,
                content=ft.Column([single_tab_bar, single_tab_view], expand=True, spacing=0),
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

        self._page_ref.run_task(_update_timer)

    def _stop_timer(self):
        """停止計時器"""
        self._timer_running = False

    # ── Mic Live 音量 poll（ui_spec §2.5）──

    def _start_level_poll(self):
        """會中啟動 Mic Live 音量 poll，每 poll_interval_ms 更新一次"""
        if not self._audio_recorder:
            return
        self._level_poll_running = True
        interval = self._mic_poll_ms / 1000.0

        async def _poll_level():
            silent_streak = 0  # 連續靜音 tick 數
            silent_warned = False
            while self._level_poll_running:
                dbfs = self._audio_recorder.get_current_level()
                self._update_mic_level_ui(dbfs)
                # 無障礙：靜音 > 3 秒 SnackBar 警訊
                if dbfs < self._mic_thresholds["silent"]:
                    silent_streak += 1
                    if not silent_warned and silent_streak * interval >= 3.0:
                        silent_warned = True
                        self._show_snackbar("麥克風訊號極弱，請檢查設定")
                else:
                    silent_streak = 0
                    silent_warned = False
                await asyncio.sleep(interval)

        self._page_ref.run_task(_poll_level)

    def _stop_level_poll(self):
        """停止 Mic Live poll"""
        self._level_poll_running = False

    def set_audio_recorder(self, recorder: AudioRecorder):
        """外部注入 AudioRecorder（Bug #15 修復）。

        main.py 在 constructor 階段 recorder 仍是 None；實際 recorder 於
        on_start_recording 時才建立。此 setter 讓 main.py 把新建的 recorder
        注入到 dashboard 內部，避免 Python closure late-binding 陷阱。
        """
        self._audio_recorder = recorder
        # 若 Mic Live poll 已在跑，重啟 binding 到新 recorder
        if self._level_poll_running:
            self._stop_level_poll()
            self._start_level_poll()

    # ── Mic Test 模式（ui_spec §2.5 閒置預覽）──

    def _handle_mic_test(self, e):
        """啟動 5 秒 Mic Test — 不建 session、不寫 WAV。

        Bug #15 A1 fallback：idle 階段 _audio_recorder 可能是 None（main.py
        尚未進 on_start_recording），此時臨時建一個 AudioRecorder 做 probe，
        倒數結束後在 _stop_mic_test 清理。
        """
        if self._level_poll_running:
            return

        # A1 fallback：若尚無 recorder，臨時建一個做 probe
        temp_recorder = None
        if self._audio_recorder is None:
            try:
                temp_recorder = AudioRecorder(self.config)
            except Exception:
                # config 或 sounddevice 缺失時放棄測試（避免 UI dead）
                return
            active_recorder = temp_recorder
        else:
            active_recorder = self._audio_recorder
        self._mic_test_temp_recorder = temp_recorder  # _stop_mic_test 清理用

        # 建立 Mic Test UI
        self._mic_test_bar = ft.ProgressBar(
            value=0, width=200, bar_height=12,
            color=COLOR_GREEN, bgcolor=COLOR_SURFACE,
        )
        self._mic_test_dbfs_text = ft.Text(
            "peak: -80 dBFS", size=12, color=COLOR_TEXT_DIM,
        )
        self._mic_test_countdown = ft.Text(
            f"倒數 {self._mic_test_duration}s", size=14, color=COLOR_TEXT,
        )
        cancel_btn = ft.TextButton(
            "取消測試", on_click=lambda _: self._stop_mic_test(),
        )

        self._mic_test_container.content = ft.Column([
            ft.Container(height=10),
            ft.Text("🎤 測試麥克風", size=16, weight=ft.FontWeight.BOLD,
                     color=COLOR_TEXT),
            self._mic_test_countdown,
            self._mic_test_bar,
            self._mic_test_dbfs_text,
            cancel_btn,
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6)
        self._mic_test_container.visible = True
        if self._mounted:
            self._mic_test_container.update()

        # 啟動 probe + poll
        active_recorder.start_level_probe()
        self._level_poll_running = True

        async def _mic_test_loop():
            remaining = self._mic_test_duration
            interval = self._mic_poll_ms / 1000.0
            ticks_per_sec = int(1.0 / interval)
            tick = 0
            while self._level_poll_running and remaining > 0:
                dbfs = active_recorder.get_current_level()
                # 更新 UI
                normalized = max(0.0, min(1.0, (dbfs + 80) / 80))
                self._mic_test_bar.value = normalized
                t = self._mic_thresholds
                if dbfs >= t["clipping"]:
                    color, label = COLOR_RED, "爆音"
                elif dbfs >= t["loud"]:
                    color, label = COLOR_AMBER, "大聲"
                elif dbfs >= t["normal"]:
                    color, label = COLOR_GREEN, "正常"
                else:
                    color, label = COLOR_TEXT_DIM, "靜音"
                self._mic_test_bar.color = color
                self._mic_test_dbfs_text.value = f"peak: {dbfs:.0f} dBFS ({label})"
                tick += 1
                if tick >= ticks_per_sec:
                    remaining -= 1
                    tick = 0
                    self._mic_test_countdown.value = f"倒數 {remaining}s"
                if self._mounted:
                    try:
                        self._mic_test_bar.update()
                        self._mic_test_dbfs_text.update()
                        self._mic_test_countdown.update()
                    except Exception:
                        break
                await asyncio.sleep(interval)
            self._stop_mic_test()

        self._page_ref.run_task(_mic_test_loop)

    def _stop_mic_test(self):
        """停止 Mic Test 模式 — 含 A1 fallback 臨時 recorder 清理"""
        self._level_poll_running = False
        # 判定實際使用的 recorder：優先 temp（A1 fallback），否則既有的
        temp = getattr(self, '_mic_test_temp_recorder', None)
        active = temp if temp is not None else self._audio_recorder
        if active is not None:
            try:
                active.stop_level_probe()
            except Exception:
                pass
        self._mic_test_temp_recorder = None
        if hasattr(self, '_mic_test_container') and self._mic_test_container:
            self._mic_test_container.visible = False
            if self._mounted:
                try:
                    self._mic_test_container.update()
                except Exception:
                    pass

    def _update_mic_level_ui(self, dbfs: float):
        """更新音量條 UI — 顏色分級 + ProgressBar 值"""
        if not self._mic_level_bar:
            return
        # dBFS -80~0 映射到 0~1
        normalized = max(0.0, min(1.0, (dbfs + 80) / 80))
        self._mic_level_bar.value = normalized

        # 顏色分級
        t = self._mic_thresholds
        if dbfs >= t["clipping"]:
            color = COLOR_RED
            label = "爆音"
        elif dbfs >= t["loud"]:
            color = COLOR_AMBER
            label = "大聲"
        elif dbfs >= t["normal"]:
            color = COLOR_GREEN
            label = "正常"
        else:
            color = COLOR_TEXT_DIM
            label = "靜音"
        self._mic_level_bar.color = color

        if self._mic_level_text:
            self._mic_level_text.value = f"{dbfs:.0f} dBFS ({label})"

        if self._mounted:
            try:
                self._mic_level_bar.update()
                if self._mic_level_text:
                    self._mic_level_text.update()
            except Exception:
                pass

    # ── 底部操作 ──

    async def _handle_export(self, e):
        if not self._session or not self.exporter:
            return

        # Bug #17：FilePicker 是 service control，必須先在 page.overlay
        # 才能透過 session dispatch 到 client；否則 save_file 炸 Session closed
        picker = ft.FilePicker()
        self._page_ref.overlay.append(picker)
        self._page_ref.update()
        try:
            path = await picker.save_file(
                dialog_title="匯出 Markdown",
                file_name=f"{self._session.title}.md",
                allowed_extensions=["md"],
            )
            if path:
                self._save_user_edits()
                self.exporter.export(self._session, path)
                self.session_mgr.save(self._session)
                # 匯出後詢問是否刪除音檔（ui_spec#7）
                self._show_delete_audio_dialog()
        finally:
            if picker in self._page_ref.overlay:
                self._page_ref.overlay.remove(picker)
                self._page_ref.update()

    def _show_delete_audio_dialog(self):
        def _delete(e):
            self.session_mgr.delete_audio(self._session)
            self.session_mgr.save(self._session)
            self._page_ref.pop_dialog()

        def _keep(e):
            self._page_ref.pop_dialog()

        dlg = ft.AlertDialog(
            title=ft.Text("匯出完成"),
            content=ft.Text("是否刪除原始音檔？"),
            actions=[
                ft.TextButton("保留", on_click=_keep),
                ft.ElevatedButton("刪除", on_click=_delete,
                                  style=ft.ButtonStyle(bgcolor=COLOR_RED, color=COLOR_TEXT)),
            ],
        )
        self._page_ref.show_dialog(dlg)

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
            self._page_ref.pop_dialog()
            self.set_mode("idle")

        dlg = ft.AlertDialog(
            title=ft.Text("確定刪除此會議紀錄？"),
            content=ft.Text("此操作無法復原。"),
            actions=[
                ft.TextButton("取消", on_click=lambda e: self._page_ref.pop_dialog()),
                ft.ElevatedButton("確定", on_click=_confirm,
                                  style=ft.ButtonStyle(bgcolor=COLOR_RED, color=COLOR_TEXT)),
            ],
        )
        self._page_ref.show_dialog(dlg)

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
        self._page_ref.show_dialog(ft.SnackBar(content=ft.Text(msg)))

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
