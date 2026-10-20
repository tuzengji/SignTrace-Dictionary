"""Verify public data fields, JSONL correspondence and every original image."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from export_original import SIGN_COLUMNS, MEANING_COLUMNS, row_digest


def verify(data_dir):
    data_dir = data_dir.resolve(strict=True)
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    actual = {p.relative_to(data_dir).as_posix() for p in data_dir.rglob("*") if p.is_file()}
    assert actual == set(manifest["files"]) | {"manifest.json"}, "Unexpected or missing data files"
    assert not any(p.is_symlink() for p in data_dir.rglob("*")), "Public data must contain real files"
    for name, metadata in manifest["files"].items():
        path = (data_dir / name).resolve(strict=True)
        assert path.is_relative_to(data_dir), "Unsafe manifest path"
        data = path.read_bytes()
        assert len(data) == metadata["bytes"], name
        assert hashlib.sha256(data).hexdigest() == metadata["sha256"], name

    with closing(sqlite3.connect((data_dir / "signs.db").as_uri() + "?mode=ro", uri=True)) as db:
        assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        assert db.execute("PRAGMA freelist_count").fetchone()[0] == 0
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
        assert tables == {"signs", "meanings"}, "Unexpected tables"
        assert not db.execute("SELECT name FROM sqlite_schema WHERE type IN ('view', 'trigger')").fetchall()
        rows = {}
        for table, columns in (("signs", SIGN_COLUMNS), ("meanings", MEANING_COLUMNS)):
            assert tuple(row[1] for row in db.execute(f"PRAGMA table_info({table})")) == columns
            rows[table] = db.execute(f"SELECT {','.join(columns)} FROM {table} ORDER BY id").fetchall()
            assert len(rows[table]) == manifest["counts"][table]
            assert row_digest(rows[table]) == manifest["original_rows_sha256"][table]

    entries = [json.loads(line) for line in (data_dir / "signs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(entries) == len(rows["signs"])
    json_meanings = []
    images = set()
    for entry, row in zip(entries, rows["signs"]):
        assert set(entry) == set(SIGN_COLUMNS) | {"meanings"}
        assert tuple(entry[key] for key in SIGN_COLUMNS) == row
        for meaning in entry["meanings"]:
            assert set(meaning) == set(MEANING_COLUMNS)
            assert meaning["sign_id"] == entry["id"]
            json_meanings.append(tuple(meaning[key] for key in MEANING_COLUMNS))
        image = (data_dir / entry["image_path"]).resolve(strict=True)
        assert image.is_relative_to(data_dir / "images")
        assert image.suffix == ".jpg" and image.read_bytes().startswith(b"\xff\xd8\xff")
        images.add(entry["image_path"])
    assert sorted(json_meanings) == rows["meanings"]
    assert images == {name for name in manifest["files"] if name.startswith("images/")}
    assert len(images) == manifest["counts"]["images"]
    return manifest["counts"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_dir", nargs="?", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    print(json.dumps({"verified": True, **verify(parser.parse_args().data_dir)}))
