"""
Attendance viewer – Gradio UI
Usage:
    /root/miniconda3/envs/wx/bin/python view.py
"""

import shutil
from pathlib import Path
import duckdb
import pandas as pd
import gradio as gr

DB_SRC    = Path(__file__).parent / 'data' / 'attend.duckdb'
DB_COPY   = Path(__file__).parent / 'data' / 'attend_view.duckdb'
PAGE_SIZE = 10

DISPLAY_COLS = [
    'indexNo', 'week', 'day', 'date', 'time', 'room',
    'moduleCode', 'moduleName', 'lecturer', 'year', 'programme',
    'class_', 'totalStudentNum', 'studentNumInClassroom',
    'percent', 'by', 'photoUploaded', 'remark',
]


def _copy_db():
    """Copy the live DB to a local snapshot so we avoid lock conflicts."""
    shutil.copy2(DB_SRC, DB_COPY)


def _con():
    return duckdb.connect(str(DB_COPY), read_only=True)


def _load_dates():
    con = _con()
    rows = con.execute(
        "SELECT DISTINCT date, day FROM attend ORDER BY date"
    ).fetchall()
    con.close()
    labels  = [f"{r[0]}  ({r[1]})" for r in rows]
    mapping = {f"{r[0]}  ({r[1]})": r[0] for r in rows}
    return labels, mapping


def _records_for_date(date_str: str) -> pd.DataFrame:
    con = _con()
    df = con.execute(
        "SELECT * FROM attend WHERE date=? ORDER BY time, indexNo",
        [date_str],
    ).df()
    con.close()
    return df[DISPLAY_COLS] if set(DISPLAY_COLS).issubset(df.columns) else df


def _page_slice(df: pd.DataFrame, page: int):
    total_pages = max(1, (len(df) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    return df.iloc[start : start + PAGE_SIZE], page, total_pages


# ── Event callbacks ────────────────────────────────────────────────────────

def on_date_change(date_label):
    date_map = _load_dates()[1]
    date_str = date_map.get(date_label, "")
    df = _records_for_date(date_str)
    sliced, page, total = _page_slice(df, 1)
    info = f"第 1 / {total} 页  （共 {len(df)} 条）"
    return sliced, info, page, total, df


def on_prev(page, total_pages, full_df):
    sliced, page, total = _page_slice(full_df, page - 1)
    info = f"第 {page} / {total} 页  （共 {len(full_df)} 条）"
    return sliced, info, page


def on_next(page, total_pages, full_df):
    sliced, page, total = _page_slice(full_df, page + 1)
    info = f"第 {page} / {total} 页  （共 {len(full_df)} 条）"
    return sliced, info, page


def on_refresh(date_label):
    """Re-copy DB then reload current date from page 1."""
    _copy_db()
    date_labels, date_map = _load_dates()
    # Keep current selection if still valid, else fall back to first
    if date_label not in date_map:
        date_label = date_labels[0] if date_labels else ""
    date_str = date_map.get(date_label, "")
    df = _records_for_date(date_str)
    sliced, page, total = _page_slice(df, 1)
    info = f"第 1 / {total} 页  （共 {len(df)} 条）"
    return gr.update(choices=date_labels, value=date_label), sliced, info, page, total, df


def on_search(index_no_str: str):
    index_no_str = index_no_str.strip()
    if not index_no_str:
        return pd.DataFrame(columns=DISPLAY_COLS)
    try:
        idx = int(index_no_str)
    except ValueError:
        return pd.DataFrame({"错误": ["请输入有效的整数 Index No."]})
    con = _con()
    df = con.execute("SELECT * FROM attend WHERE indexNo=?", [idx]).df()
    con.close()
    if df.empty:
        return pd.DataFrame({"结果": [f"未找到 indexNo={idx} 的记录"]})
    return df[DISPLAY_COLS] if set(DISPLAY_COLS).issubset(df.columns) else df


# ── Initial copy ───────────────────────────────────────────────────────────
_copy_db()
DATE_LABELS, DATE_MAP = _load_dates()

# ── UI ─────────────────────────────────────────────────────────────────────
with gr.Blocks(title="考勤查看器") as demo:
    gr.Markdown("# 考勤查看器")

    cur_page       = gr.State(1)
    total_pages_st = gr.State(1)
    full_df_st     = gr.State(pd.DataFrame())

    with gr.Row():
        date_dd     = gr.Dropdown(
            choices=DATE_LABELS,
            value=DATE_LABELS[0] if DATE_LABELS else None,
            label="选择日期",
            scale=4,
        )
        refresh_btn = gr.Button("🔄 刷新数据", scale=1)

    with gr.Row():
        prev_btn  = gr.Button("← 上一页", scale=1)
        page_info = gr.Textbox(value="", label="页码", interactive=False, scale=2)
        next_btn  = gr.Button("下一页 →", scale=1)

    table = gr.Dataframe(label="考勤记录", wrap=True, interactive=False)

    date_dd.change(
        on_date_change,
        inputs=[date_dd],
        outputs=[table, page_info, cur_page, total_pages_st, full_df_st],
    )

    prev_btn.click(
        on_prev,
        inputs=[cur_page, total_pages_st, full_df_st],
        outputs=[table, page_info, cur_page],
    )

    next_btn.click(
        on_next,
        inputs=[cur_page, total_pages_st, full_df_st],
        outputs=[table, page_info, cur_page],
    )

    refresh_btn.click(
        on_refresh,
        inputs=[date_dd],
        outputs=[date_dd, table, page_info, cur_page, total_pages_st, full_df_st],
    )

    demo.load(
        on_date_change,
        inputs=[date_dd],
        outputs=[table, page_info, cur_page, total_pages_st, full_df_st],
    )

    gr.Markdown("---")
    gr.Markdown("## 按 Index No. 查找")

    with gr.Row():
        search_input = gr.Textbox(
            label="Index No.",
            placeholder="输入整数 Index No. 后按 Enter 或点击查找",
            scale=3,
        )
        search_btn = gr.Button("查找", scale=1)

    search_result = gr.Dataframe(label="查找结果", interactive=False)

    search_btn.click(on_search, inputs=[search_input], outputs=[search_result])
    search_input.submit(on_search, inputs=[search_input], outputs=[search_result])


if __name__ == '__main__':
    demo.launch(server_name='127.0.0.1', server_port=17801)
