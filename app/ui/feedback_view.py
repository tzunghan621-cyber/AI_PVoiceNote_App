"""回饋統計頁 — ui_spec#4"""

from __future__ import annotations

import flet as ft

from app.ui.main_view import (
    COLOR_BG, COLOR_SURFACE, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT,
    COLOR_AMBER, COLOR_GREEN, COLOR_RED,
)


class FeedbackView(ft.Container):
    def __init__(self, knowledge_base, feedback_store):
        self.kb = knowledge_base
        self.feedback_store = feedback_store
        self._content = ft.Column(expand=True, spacing=8, scroll=ft.ScrollMode.AUTO)
        super().__init__(content=self._content, expand=True, bgcolor=COLOR_BG, padding=15)
        self.refresh()

    def refresh(self):
        self._content.controls.clear()
        self._content.controls.append(
            ft.Text("回饋統計", size=20, weight=ft.FontWeight.BOLD, color=COLOR_TEXT)
        )
        self._content.controls.append(ft.Divider(color=COLOR_SURFACE))

        # 整體統計
        self._build_overview()
        # 需要關注區
        self._build_attention_section()
        # 最近 Session 回饋
        self._build_recent_sessions()

        self._content.update()

    def _build_overview(self):
        term_stats = self.feedback_store.get_term_stats()
        all_fb = self.feedback_store.list_all()

        total_correct = sum(s.get("correct", 0) for s in term_stats.values())
        total_wrong = sum(s.get("wrong", 0) for s in term_stats.values())
        total_missed = sum(s.get("missed", 0) for s in term_stats.values())
        total = total_correct + total_wrong + total_missed
        success_rate = (total_correct / (total_correct + total_wrong) * 100) if (total_correct + total_wrong) > 0 else 0

        # 進度條
        bar_width = 200
        filled = int(bar_width * success_rate / 100)
        progress = ft.Container(
            content=ft.Row([
                ft.Container(bgcolor=COLOR_GREEN, width=filled, height=12, border_radius=6),
                ft.Container(bgcolor=COLOR_SURFACE, expand=True, height=12, border_radius=6),
            ], spacing=0, width=bar_width),
        )

        cards = ft.Row([
            self._stat_card("整體校正成功率", f"{success_rate:.0f}%", progress),
            self._stat_card("總回饋數", str(total), None),
            self._stat_card("總 Session 數", str(len(all_fb)), None),
        ], spacing=10, wrap=True)

        self._content.controls.append(cards)
        self._content.controls.append(ft.Divider(color=COLOR_SURFACE))

    def _stat_card(self, label: str, value: str, extra: ft.Control | None) -> ft.Container:
        controls = [
            ft.Text(label, size=11, color=COLOR_TEXT_DIM),
            ft.Text(value, size=22, weight=ft.FontWeight.BOLD, color=COLOR_TEXT),
        ]
        if extra:
            controls.append(extra)
        return ft.Container(
            content=ft.Column(controls, spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=COLOR_SURFACE,
            border_radius=8,
            padding=15,
            width=200,
            alignment=ft.alignment.center,
        )

    def _build_attention_section(self):
        self._content.controls.append(
            ft.Text("⚠️ 需要關注", size=16, weight=ft.FontWeight.BOLD, color=COLOR_AMBER)
        )

        term_stats = self.feedback_store.get_term_stats()
        terms = self.kb.list_terms()
        terms_by_id = {t["id"]: t for t in terms}

        # 低成功率詞條（< 50%）
        low_perf = []
        for tid, stats in term_stats.items():
            total = stats.get("correct", 0) + stats.get("wrong", 0)
            if total > 0:
                rate = stats["correct"] / total
                if rate < 0.5:
                    name = terms_by_id.get(tid, {}).get("term", tid)
                    low_perf.append((name, rate))

        if low_perf:
            self._content.controls.append(
                ft.Text("低成功率詞條（< 50%）：", size=13, color=COLOR_TEXT)
            )
            for name, rate in low_perf:
                self._content.controls.append(
                    ft.Text(f"  · {name} — 成功率 {rate*100:.0f}%", size=12, color=COLOR_RED)
                )
        else:
            self._content.controls.append(
                ft.Text("低成功率詞條：無", size=12, color=COLOR_TEXT_DIM)
            )

        # 零命中詞條
        zero_hit = [t for t in terms if t.get("stats", {}).get("hit_count", 0) == 0]
        if zero_hit:
            self._content.controls.append(
                ft.Text("零命中詞條（可能無效）：", size=13, color=COLOR_TEXT)
            )
            for t in zero_hit[:10]:
                self._content.controls.append(
                    ft.Text(f"  · {t['term']}", size=12, color=COLOR_TEXT_DIM)
                )
        else:
            self._content.controls.append(
                ft.Text("零命中詞條：無", size=12, color=COLOR_TEXT_DIM)
            )

        # 高頻遺漏
        misses = self.feedback_store.get_high_frequency_misses(threshold=3)
        if misses:
            self._content.controls.append(
                ft.Text("高頻遺漏回報（應新增詞條）：", size=13, color=COLOR_TEXT)
            )
            for text in misses:
                self._content.controls.append(
                    ft.Text(f"  · 「{text}」", size=12, color=COLOR_AMBER)
                )
        else:
            self._content.controls.append(
                ft.Text("高頻遺漏回報：無", size=12, color=COLOR_TEXT_DIM)
            )

        self._content.controls.append(ft.Divider(color=COLOR_SURFACE))

    def _build_recent_sessions(self):
        self._content.controls.append(
            ft.Text("最近 Session 回饋", size=16, weight=ft.FontWeight.BOLD, color=COLOR_TEXT)
        )

        all_fb = self.feedback_store.list_all()
        for fb in reversed(all_fb[-10:]):
            correct = sum(1 for e in fb.entries if e.type == "correct")
            total = sum(1 for e in fb.entries if e.type in ("correct", "wrong"))
            rate = (correct / total * 100) if total > 0 else 0
            self._content.controls.append(
                ft.Text(
                    f"  {fb.created[:16]} — 校正 {correct}/{total} 正確 ({rate:.0f}%)",
                    size=12, color=COLOR_TEXT_DIM,
                )
            )

        if not all_fb:
            self._content.controls.append(
                ft.Text("  尚無回饋紀錄", size=12, color=COLOR_TEXT_DIM)
            )
