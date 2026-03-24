from backfill import build_backfill_markdown


def test_build_backfill_markdown_groups_missing_days_and_uses_bufa_name(tmp_path):
    path, body = build_backfill_markdown(
        output_dir=str(tmp_path),
        date_sections={
            "2026-03-12": "# 2026-03-12\n内容A",
            "2026-03-14": "# 2026-03-14\n内容B",
        },
    )
    assert "补发" in path.name
    assert "2026-03-12" in body
    assert "2026-03-14" in body
