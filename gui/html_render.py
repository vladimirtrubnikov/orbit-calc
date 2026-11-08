"""gui/html_render.py — stdout _solve_* → цветной HTML."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Any


COLOR = {
    "h2":    "#c084fc",
    "step":  "#60a5fa",
    "final": "#4ade80",
    "err":   "#ef4444",
    "vec":   "#fbbf24",
    "info":  "#94a3b8",
    "num":   "#fbbf24",
}


def _esc(s: str) -> str:
    return _html.escape(s)


def render(stdout: str, output: dict[str, Any], error: str | None = None) -> str:
    parts: list[str] = []
    if error:
        parts.append(f'<div class="err"><b>Ошибка:</b> {_esc(error)}</div>')

    in_final = False
    in_table = False

    for raw in stdout.splitlines():
        line = raw.rstrip()
        if not line.strip():
            if in_table:
                parts.append("</table>")
                in_table = False
            in_final = False
            parts.append("<div style='height:4px'></div>")
            continue

        m = re.match(r"\s*(СЛУЧАЙ \d+:[^─]+)", line)
        if m:
            parts.append(
                f'<h2 style="color:{COLOR["h2"]};border-bottom:1px solid #333;'
                f'padding:6px 0;">{_esc(m.group(1).strip())}</h2>'
            )
            continue

        if line.strip().startswith("──"):
            title = line.strip().strip("─ ").strip()
            if title:
                color = COLOR["final"] if "ИТОГ" in title.upper() else COLOR["h2"]
                parts.append(f'<h3 style="color:{color};margin-top:14px;">'
                             f'{_esc(title)}</h3>')
            if "ИТОГ" in title.upper():
                in_final = True
            continue

        m = re.match(r"\s*Шаг (\d+):\s*(.*)", line)
        if m:
            n, body = m.groups()
            parts.append(
                f'<div style="color:{COLOR["step"]};padding:2px 0 2px 8px;'
                f'font-family:monospace;"><b>Шаг {n}:</b> '
                f'<span style="color:#d4d4d4">{_esc(body)}</span></div>'
            )
            continue

        m = re.match(r"\s*(N=\d+,\s*\w+:)", line)
        if m:
            parts.append(f'<div style="color:{COLOR["vec"]};margin-top:6px;">'
                         f'<b>{_esc(m.group(1))}</b></div>')
            continue

        if re.match(r"\s*v[12]\s*=", line):
            parts.append(f'<div style="color:#d4d4d4;font-family:monospace;'
                         f'padding-left:16px;">{_esc(line.strip())}</div>')
            continue

        if "Найдено решений" in line:
            parts.append(f'<div style="color:{COLOR["info"]};font-style:italic;">'
                         f'{_esc(line.strip())}</div>')
            continue

        m = re.match(r"\s*([^:]+):\s+([-+]?[\d.,]+(?:\s+\S+)?)\s*$", line)
        if m and in_final:
            k, v = m.groups()
            if not in_table:
                parts.append('<table style="border-collapse:collapse;margin:6px 0;">')
                in_table = True
            parts.append(
                f'<tr><td style="padding:2px 20px 2px 0;color:#94a3b8;">'
                f'{_esc(k.strip())}</td>'
                f'<td style="padding:2px 0;color:{COLOR["num"]};'
                f'font-family:monospace;font-weight:bold;">{_esc(v.strip())}</td></tr>'
            )
            continue

        parts.append(f'<div style="color:#c0c0c0;font-family:monospace;">'
                     f'{_esc(line)}</div>')

    if in_table:
        parts.append("</table>")

    if output:
        parts.append(
            '<div style="margin-top:20px;padding:12px;background:#1a1a2e;'
            'border-left:3px solid #8b5cf6;border-radius:4px;">'
            '<div style="color:#8b5cf6;font-weight:bold;margin-bottom:6px;">'
            'Данные для экспорта (JSON)</div>'
            f'<pre style="color:#d4d4d4;margin:0;font-size:11px;">'
            f'{_esc(json.dumps(output, indent=2, ensure_ascii=False, default=str))}'
            '</pre></div>'
        )

    style = """
    <style>
        body { background:#0f0f18; color:#d4d4d4;
               font-family:'Monospace','Consolas',monospace;
               font-size:12px; line-height:1.55; }
        table { border-collapse:collapse; }
        .err { background:#3a0f0f; color:#ef4444; padding:10px;
               border-radius:6px; border-left:3px solid #ef4444;
               margin-bottom:12px; }
    </style>
    """
    return style + "<body>" + "".join(parts) + "</body>"
