"""設定頁面 — ui_spec#5"""

from __future__ import annotations

import flet as ft

from app.data.config_manager import ConfigManager
from app.ui.main_view import COLOR_BG, COLOR_SURFACE, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT


class SettingsView(ft.Container):
    def __init__(self, config: ConfigManager):
        self.config = config
        self._fields: dict[str, ft.Control] = {}
        content = self._build()
        super().__init__(content=content, expand=True, bgcolor=COLOR_BG, padding=20)

    def _build(self) -> ft.Column:
        return ft.Column([
            ft.Text("設定", size=20, weight=ft.FontWeight.BOLD, color=COLOR_TEXT),
            ft.Divider(color=COLOR_SURFACE),
            self._section("🔊 語音轉文字", [
                self._dropdown("Whisper 模型", ["tiny", "small", "medium", "large"],
                               "whisper.model"),
                self._dropdown("語言", ["zh", "en", "ja"], "whisper.language"),
            ]),
            self._section("🤖 摘要模型", [
                self._text_field("Ollama 位址", "ollama.base_url"),
                self._dropdown("模型", ["gemma4:e2b", "gemma4:e4b"],
                               "ollama.model"),
            ]),
            self._section("⏱️ 串流處理", [
                self._text_field("摘要更新週期（秒）", "streaming.summary_interval_sec", number=True),
                self._text_field("最少新段落數", "streaming.summary_min_new_segments", number=True),
            ]),
            self._section("📚 App 知識庫", [
                self._text_field("詞條目錄", "knowledge_base.terms_dir"),
                self._text_field("向量索引目錄", "knowledge_base.chroma_dir"),
            ]),
            self._section("📁 匯出", [
                self._text_field("預設匯出目錄", "export.default_dir"),
                self._checkbox("包含原始逐字稿", "export.include_raw_transcript"),
                self._checkbox("包含校正標記", "export.include_corrections"),
            ]),
            self._section("🎤 音訊", [
                self._text_field("取樣率", "audio.sample_rate", number=True),
            ]),
            ft.Container(height=10),
            ft.Row([
                ft.ElevatedButton("儲存設定", icon=ft.Icons.SAVE,
                                  bgcolor=COLOR_ACCENT, color=COLOR_TEXT,
                                  on_click=self._save),
                ft.OutlinedButton("恢復預設", on_click=self._reset),
            ], spacing=10),
        ], scroll=ft.ScrollMode.AUTO, spacing=8, expand=True)

    def _section(self, title: str, controls: list[ft.Control]) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color=COLOR_TEXT),
                *controls,
            ], spacing=8),
            padding=ft.padding.only(top=10, bottom=5),
        )

    def _text_field(self, label: str, config_key: str, number: bool = False) -> ft.TextField:
        val = self.config.get(config_key, "")
        field = ft.TextField(
            label=label, value=str(val),
            border_color=COLOR_SURFACE, color=COLOR_TEXT,
            label_style=ft.TextStyle(color=COLOR_TEXT_DIM),
            keyboard_type=ft.KeyboardType.NUMBER if number else None,
            dense=True,
        )
        self._fields[config_key] = field
        return field

    def _dropdown(self, label: str, options: list[str], config_key: str) -> ft.Dropdown:
        current = str(self.config.get(config_key, ""))
        dd = ft.Dropdown(
            label=label,
            value=current if current in options else options[0],
            options=[ft.dropdown.Option(o) for o in options],
            border_color=COLOR_SURFACE, color=COLOR_TEXT,
            label_style=ft.TextStyle(color=COLOR_TEXT_DIM),
            dense=True,
        )
        self._fields[config_key] = dd
        return dd

    def _checkbox(self, label: str, config_key: str) -> ft.Checkbox:
        val = self.config.get(config_key, False)
        cb = ft.Checkbox(
            label=label, value=bool(val),
            label_style=ft.TextStyle(color=COLOR_TEXT),
        )
        self._fields[config_key] = cb
        return cb

    def _save(self, e):
        for key, control in self._fields.items():
            if isinstance(control, ft.Checkbox):
                self.config.set(key, control.value)
            elif isinstance(control, (ft.TextField, ft.Dropdown)):
                val = control.value
                # 嘗試轉為數字
                try:
                    val = int(val)
                except (ValueError, TypeError):
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        pass
                self.config.set(key, val)
        self.config.save()
        if hasattr(self, 'page') and self.page:
            self.page.snack_bar = ft.SnackBar(content=ft.Text("設定已儲存"))
            self.page.snack_bar.open = True
            self.page.update()

    def _reset(self, e):
        import shutil
        # 重新載入預設設定
        self.config.__init__(self.config._path)
        # 更新 UI
        for key, control in self._fields.items():
            val = self.config.get(key, "")
            if isinstance(control, ft.Checkbox):
                control.value = bool(val)
            elif isinstance(control, (ft.TextField, ft.Dropdown)):
                control.value = str(val)
            control.update()
