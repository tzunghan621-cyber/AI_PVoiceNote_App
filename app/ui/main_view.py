"""主視窗 — 左側導航 + 主內容區 + 底部狀態列"""

from __future__ import annotations

import os
from pathlib import Path

import flet as ft

from app.data.config_manager import ConfigManager

# 色彩常數（ui_spec#8）
COLOR_BG = "#1e1e2e"
COLOR_SURFACE = "#2a2a3c"
COLOR_NAV = "#252536"
COLOR_TEXT = "#cdd6f4"
COLOR_TEXT_DIM = "#6c7086"
COLOR_ACCENT = "#89b4fa"  # 藍
COLOR_AMBER = "#fab387"   # 琥珀（校正高亮）
COLOR_GREEN = "#a6e3a1"   # 成功
COLOR_RED = "#f38ba8"     # 錯誤


class StatusBar(ft.Container):
    """底部狀態列 — ui_spec#6"""

    def __init__(self, config: ConfigManager):
        self.config = config
        self._ollama_status = ft.Text("🔴 Ollama 未連線", size=12, color=COLOR_TEXT_DIM)
        self._model_name = ft.Text(
            config.get("ollama.model", "gemma3:4b"), size=12, color=COLOR_TEXT_DIM
        )
        self._term_count = ft.Text("0 筆詞條", size=12, color=COLOR_TEXT_DIM)
        self._temp_usage = ft.Text("暫存: 0MB", size=12, color=COLOR_TEXT_DIM)
        self._summary_time = ft.Text("", size=12, color=COLOR_TEXT_DIM, visible=False)

        super().__init__(
            content=ft.Row(
                [
                    self._ollama_status,
                    ft.VerticalDivider(width=1, color=COLOR_TEXT_DIM),
                    self._model_name,
                    ft.VerticalDivider(width=1, color=COLOR_TEXT_DIM),
                    self._term_count,
                    ft.VerticalDivider(width=1, color=COLOR_TEXT_DIM),
                    self._temp_usage,
                    self._summary_time,
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.START,
            ),
            bgcolor=COLOR_NAV,
            padding=ft.padding.symmetric(horizontal=15, vertical=6),
            height=32,
        )

    def update_ollama(self, connected: bool, loading: bool = False):
        if loading:
            self._ollama_status.value = "🟡 模型載入中"
        elif connected:
            self._ollama_status.value = "🟢 Ollama 已連線"
        else:
            self._ollama_status.value = "🔴 Ollama 未連線"
        self._ollama_status.update()

    def update_term_count(self, count: int):
        self._term_count.value = f"{count} 筆詞條"
        self._term_count.update()

    def update_temp_usage(self):
        temp_dir = self.config.get("audio.temp_dir", "data/temp")
        try:
            total = sum(f.stat().st_size for f in Path(temp_dir).glob("*") if f.is_file())
            mb = total / (1024 * 1024)
            self._temp_usage.value = f"暫存: {mb:.0f}MB"
        except Exception:
            self._temp_usage.value = "暫存: --"
        self._temp_usage.update()

    def set_meeting_mode(self, active: bool, last_summary: str = "", next_summary: str = ""):
        if active:
            self._summary_time.visible = True
            self._summary_time.value = f"│ 上次摘要: {last_summary} │ 下次: ~{next_summary}"
        else:
            self._summary_time.visible = False
        self._summary_time.update()


class MainView:
    """主視窗佈局 — ui_spec#1"""

    def __init__(self, config: ConfigManager):
        self.config = config
        self.page: ft.Page | None = None
        self.status_bar = StatusBar(config)
        self.content_area = ft.Container(expand=True, bgcolor=COLOR_BG)
        self._views: dict[int, ft.Control] = {}
        self._current_view_index = 0

        # 延遲設定：各頁面由外部注入
        self.dashboard_view: ft.Control | None = None
        self.terms_view: ft.Control | None = None
        self.feedback_view: ft.Control | None = None
        self.settings_view: ft.Control | None = None

    def build(self, page: ft.Page):
        self.page = page
        page.title = "語音會議摘要筆記"
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = COLOR_BG
        page.window.min_width = 800
        page.window.min_height = 600
        page.padding = 0
        page.spacing = 0

        # 頂部標題列
        title_bar = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.RECORD_VOICE_OVER, color=COLOR_ACCENT, size=24),
                    ft.Text("語音會議摘要筆記", size=16, weight=ft.FontWeight.BOLD,
                            color=COLOR_TEXT),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.SETTINGS,
                        icon_color=COLOR_TEXT_DIM,
                        tooltip="設定",
                        on_click=lambda _: self._navigate(3),
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=COLOR_NAV,
            padding=ft.padding.symmetric(horizontal=15, vertical=8),
            height=48,
        )

        # 左側導航列
        self.nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=80,
            min_extended_width=80,
            bgcolor=COLOR_NAV,
            indicator_color=COLOR_ACCENT,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.MIC_OUTLINED, selected_icon=ft.Icons.MIC,
                    label="會議",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.BOOK_OUTLINED, selected_icon=ft.Icons.BOOK,
                    label="詞條",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.ANALYTICS_OUTLINED, selected_icon=ft.Icons.ANALYTICS,
                    label="回饋",
                ),
            ],
            on_change=lambda e: self._navigate(e.control.selected_index),
        )

        # 主佈局
        body = ft.Row(
            [
                self.nav_rail,
                ft.VerticalDivider(width=1, color=COLOR_SURFACE),
                self.content_area,
            ],
            expand=True,
            spacing=0,
        )

        page.add(
            ft.Column(
                [title_bar, body, self.status_bar],
                expand=True,
                spacing=0,
            )
        )

        # 顯示首頁
        self._navigate(0)

    def _navigate(self, index: int):
        self._current_view_index = index
        if hasattr(self, 'nav_rail'):
            self.nav_rail.selected_index = index

        views = [
            self.dashboard_view,
            self.terms_view,
            self.feedback_view,
            self.settings_view,
        ]
        view = views[index] if index < len(views) else None

        if view:
            self.content_area.content = view
        else:
            self.content_area.content = ft.Container(
                content=ft.Text("載入中...", color=COLOR_TEXT_DIM),
                alignment=ft.alignment.center,
                expand=True,
            )

        if self.page:
            self.content_area.update()
            self.nav_rail.update()
