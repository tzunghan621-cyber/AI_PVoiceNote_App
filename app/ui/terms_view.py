"""詞條管理頁 — ui_spec#3"""

from __future__ import annotations

from datetime import date

import flet as ft
import yaml

from app.ui.main_view import (
    COLOR_BG, COLOR_SURFACE, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT,
    COLOR_AMBER, COLOR_GREEN, COLOR_RED,
)

ORIGIN_ICONS = {"obsidian_sync": "🔗", "manual": "✋", "auto_suggest": "💡"}


class TermsView(ft.Container):
    def __init__(self, page: ft.Page, knowledge_base):
        self.page = page
        self.kb = knowledge_base
        self._search_query = ""
        self._filter_category = None
        self._terms_list = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO, expand=True)
        self._footer = ft.Text("", size=12, color=COLOR_TEXT_DIM)

        content = self._build()
        super().__init__(content=content, expand=True, bgcolor=COLOR_BG, padding=15)
        self.refresh()

    def _build(self) -> ft.Column:
        search = ft.TextField(
            hint_text="🔍 搜尋詞條...",
            border_color=COLOR_SURFACE, color=COLOR_TEXT,
            on_change=self._on_search,
            dense=True, expand=True,
        )
        filter_dd = ft.Dropdown(
            label="篩選", value="全部",
            options=[
                ft.dropdown.Option("全部"),
                ft.dropdown.Option("🔗 Obsidian"),
                ft.dropdown.Option("✋ 手動"),
                ft.dropdown.Option("💡 自動建議"),
            ],
            on_change=self._on_filter,
            border_color=COLOR_SURFACE, color=COLOR_TEXT, dense=True, width=160,
        )

        return ft.Column([
            ft.Row([
                ft.Text("知識詞條管理", size=18, weight=ft.FontWeight.BOLD, color=COLOR_TEXT),
                ft.Container(expand=True),
                ft.ElevatedButton("+ 新增", bgcolor=COLOR_ACCENT, color=COLOR_TEXT,
                                  on_click=self._on_add),
                ft.OutlinedButton("匯入", on_click=self._on_import),
            ]),
            ft.Divider(color=COLOR_SURFACE),
            ft.Row([search, filter_dd], spacing=10),
            ft.Divider(color=COLOR_SURFACE),
            # 表頭
            ft.Container(
                content=ft.Row([
                    ft.Text("詞條", size=12, color=COLOR_TEXT_DIM, width=150),
                    ft.Text("別名", size=12, color=COLOR_TEXT_DIM, expand=True),
                    ft.Text("來源", size=12, color=COLOR_TEXT_DIM, width=50),
                    ft.Text("命中/成功", size=12, color=COLOR_TEXT_DIM, width=80),
                ]),
                padding=ft.padding.symmetric(horizontal=8),
            ),
            self._terms_list,
            ft.Divider(color=COLOR_SURFACE),
            self._footer,
        ], expand=True, spacing=6)

    def refresh(self):
        terms = self.kb.list_terms()

        # 篩選
        if self._filter_category:
            origin_map = {"🔗 Obsidian": "obsidian_sync", "✋ 手動": "manual", "💡 自動建議": "auto_suggest"}
            origin = origin_map.get(self._filter_category)
            if origin:
                terms = [t for t in terms if t.get("origin") == origin]

        # 搜尋
        if self._search_query:
            q = self._search_query.lower()
            terms = [t for t in terms if
                     q in t.get("term", "").lower() or
                     any(q in a.lower() for a in t.get("aliases", []))]

        self._terms_list.controls.clear()
        for t in terms:
            self._terms_list.controls.append(self._build_term_row(t))

        total = len(self.kb.list_terms())
        total_corr = sum(t.get("stats", {}).get("correction_count", 0) for t in self.kb.list_terms())
        total_succ = sum(t.get("stats", {}).get("success_count", 0) for t in self.kb.list_terms())
        rate = (total_succ / total_corr * 100) if total_corr > 0 else 0
        self._footer.value = f"共 {total} 筆詞條 │ 平均成功率 {rate:.0f}%"

        self._terms_list.update()
        self._footer.update()

    def _build_term_row(self, term: dict) -> ft.Container:
        stats = term.get("stats", {})
        corr = stats.get("correction_count", 0)
        succ = stats.get("success_count", 0)
        origin_icon = ORIGIN_ICONS.get(term.get("origin", ""), "?")
        aliases_str = ", ".join(term.get("aliases", [])[:3])
        if len(term.get("aliases", [])) > 3:
            aliases_str += "..."

        return ft.Container(
            content=ft.Row([
                ft.Text(term.get("term", ""), size=13, color=COLOR_TEXT, width=150,
                        weight=ft.FontWeight.BOLD),
                ft.Text(aliases_str, size=12, color=COLOR_TEXT_DIM, expand=True),
                ft.Text(origin_icon, size=14, width=50, text_align=ft.TextAlign.CENTER),
                ft.Text(f"{corr}/{succ}", size=12, color=COLOR_TEXT_DIM, width=80,
                        text_align=ft.TextAlign.CENTER),
            ]),
            on_click=lambda _, tid=term["id"]: self._on_edit(tid),
            padding=ft.padding.symmetric(horizontal=8, vertical=6),
            border_radius=4,
            ink=True,
        )

    def _on_search(self, e):
        self._search_query = e.control.value
        self.refresh()

    def _on_filter(self, e):
        val = e.control.value
        self._filter_category = val if val != "全部" else None
        self.refresh()

    def _on_add(self, e):
        self._show_edit_dialog(None)

    def _on_edit(self, term_id: str):
        term = self.kb.get_term(term_id)
        if term:
            self._show_edit_dialog(term)

    def _on_import(self, e):
        def on_result(result: ft.FilePickerResultEvent):
            if result.files:
                path = result.files[0].path
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                count = self.kb.import_yaml_batch(content)
                self.page.snack_bar = ft.SnackBar(content=ft.Text(f"已匯入 {count} 筆詞條"))
                self.page.snack_bar.open = True
                self.page.update()
                self.refresh()

        picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.pick_files(dialog_title="匯入 YAML", allowed_extensions=["yaml", "yml"])

    def _show_edit_dialog(self, term: dict | None):
        is_new = term is None
        term_field = ft.TextField(label="正式名稱", value=term.get("term", "") if term else "",
                                  border_color=COLOR_SURFACE, dense=True)
        aliases_field = ft.TextField(label="別名（逗號分隔）",
                                     value=", ".join(term.get("aliases", [])) if term else "",
                                     border_color=COLOR_SURFACE, dense=True)
        category_field = ft.TextField(label="分類", value=term.get("category", "") if term else "",
                                      border_color=COLOR_SURFACE, dense=True)
        context_field = ft.TextField(label="說明", value=term.get("context", "") if term else "",
                                     border_color=COLOR_SURFACE, dense=True, multiline=True)
        source_field = ft.TextField(label="來源", value=term.get("source", "") if term else "",
                                    border_color=COLOR_SURFACE, dense=True)

        stats_text = ""
        if term and "stats" in term:
            s = term["stats"]
            stats_text = f"命中 {s.get('hit_count',0)} │ 校正 {s.get('correction_count',0)} │ 成功 {s.get('success_count',0)} │ 失敗 {s.get('fail_count',0)}"

        def _save(ev):
            name = term_field.value.strip()
            if not name:
                return
            aliases = [a.strip() for a in aliases_field.value.split(",") if a.strip()]
            tid = term["id"] if term else name.lower().replace(" ", "_")
            today = str(date.today())

            term_dict = {
                "id": tid, "term": name, "aliases": aliases,
                "category": category_field.value.strip(),
                "context": context_field.value.strip(),
                "source": source_field.value.strip(),
                "origin": term.get("origin", "manual") if term else "manual",
                "created": term.get("created", today) if term else today,
                "updated": today,
                "stats": term.get("stats", {"hit_count": 0, "correction_count": 0,
                                             "success_count": 0, "fail_count": 0}) if term else
                         {"hit_count": 0, "correction_count": 0, "success_count": 0, "fail_count": 0},
            }
            if is_new:
                self.kb.add_term(term_dict)
            else:
                self.kb.update_term(tid, term_dict)
            dlg.open = False
            self.page.update()
            self.refresh()

        def _delete(ev):
            if term:
                self.kb.delete_term(term["id"])
            dlg.open = False
            self.page.update()
            self.refresh()

        actions = [
            ft.TextButton("取消", on_click=lambda e: setattr(dlg, 'open', False) or self.page.update()),
            ft.ElevatedButton("儲存", on_click=_save, bgcolor=COLOR_ACCENT, color=COLOR_TEXT),
        ]
        if not is_new:
            actions.insert(0, ft.TextButton("刪除", on_click=_delete,
                                            style=ft.ButtonStyle(color=COLOR_RED)))

        dlg = ft.AlertDialog(
            title=ft.Text("新增詞條" if is_new else "編輯詞條"),
            content=ft.Column([
                term_field, aliases_field, category_field,
                context_field, source_field,
                ft.Text(stats_text, size=11, color=COLOR_TEXT_DIM) if stats_text else ft.Container(),
            ], tight=True, spacing=8, width=400),
            actions=actions,
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()
