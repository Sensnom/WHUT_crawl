from __future__ import annotations

from pathlib import Path


def build_backfill_markdown(
    output_dir: str, date_sections: dict[str, str]
) -> tuple[Path, str]:
    dates = sorted(date_sections)
    if not dates:
        raise ValueError("date_sections cannot be empty")

    lines = ["# 补发通知汇总", ""]
    for current_date in dates:
        lines.extend(
            [f"## {current_date}", "", date_sections[current_date].strip(), ""]
        )
    body = "\n".join(lines).strip() + "\n"

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    file_path = output_path / (
        f"补发_summary_{dates[0].replace('-', '')}_{dates[-1].replace('-', '')}.md"
    )
    file_path.write_text(body, encoding="utf-8")
    return file_path, body
