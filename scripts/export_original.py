"""Export only original dictionary fields and referenced images, using stdlib."""
import argparse
from collections import defaultdict
from contextlib import closing
import hashlib
import json
from pathlib import Path, PurePosixPath
import sqlite3
import tempfile

SIGN_COLUMNS = ("id", "image_path", "description", "source_entry", "letter", "volume")
MEANING_COLUMNS = ("id", "sign_id", "text", "variant_index", "order_in_entry")
SCHEMA = """
CREATE TABLE signs (
    id INTEGER PRIMARY KEY,
    image_path TEXT NOT NULL,
    description TEXT NOT NULL,
    source_entry TEXT,
    letter TEXT NOT NULL,
    volume INTEGER NOT NULL
);
CREATE TABLE meanings (
    id INTEGER PRIMARY KEY,
    sign_id INTEGER NOT NULL REFERENCES signs(id),
    text TEXT NOT NULL,
    variant_index INTEGER,
    order_in_entry INTEGER
);
"""


def row_digest(rows):
    data = json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def export(source_db, images_dir, output, snapshot_date, source_version):
    source_db = source_db.resolve(strict=True)
    images_dir = images_dir.resolve(strict=True)
    if output.exists():
        raise FileExistsError("Output must be a new directory.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source_db.as_uri() + "?mode=ro", uri=True)) as source:
        source.execute("BEGIN")
        signs = source.execute(f"SELECT {','.join(SIGN_COLUMNS)} FROM signs ORDER BY id").fetchall()
        meanings = source.execute(f"SELECT {','.join(MEANING_COLUMNS)} FROM meanings ORDER BY id").fetchall()
        if not signs:
            raise ValueError("The source dictionary is empty.")
        with tempfile.TemporaryDirectory(prefix=".dictionary-export-", dir=output.parent) as temporary:
            staging = Path(temporary) / "data"
            staging.mkdir()
            # Create a fresh file: dropping columns from the enhanced database could leave old pages.
            with closing(sqlite3.connect(staging / "signs.db")) as dest:
                dest.execute("PRAGMA foreign_keys=ON")
                dest.executescript(SCHEMA)
                dest.executemany("INSERT INTO signs VALUES (?,?,?,?,?,?)", signs)
                dest.executemany("INSERT INTO meanings VALUES (?,?,?,?,?)", meanings)
                dest.commit()
                assert dest.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
                assert not dest.execute("PRAGMA foreign_key_check").fetchall()
                for table, columns, expected in (
                    ("signs", SIGN_COLUMNS, signs), ("meanings", MEANING_COLUMNS, meanings),
                ):
                    assert dest.execute(f"SELECT {','.join(columns)} FROM {table} ORDER BY id").fetchall() == expected

            by_sign = defaultdict(list)
            for row in sorted(meanings, key=lambda r: (r[1], r[4] if r[4] is not None else -1, r[0])):
                by_sign[row[1]].append(dict(zip(MEANING_COLUMNS, row)))
            with (staging / "signs.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
                for row in signs:
                    entry = dict(zip(SIGN_COLUMNS, row))
                    entry["meanings"] = by_sign[row[0]]
                    stream.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")

            image_paths = sorted({row[1] for row in signs})
            for relative in image_paths:
                path = PurePosixPath(relative)
                if path.is_absolute() or ".." in path.parts or len(path.parts) < 2 or path.parts[0] != "images":
                    raise ValueError("Unsafe image path in source database.")
                original = (images_dir / Path(*path.parts[1:])).resolve(strict=True)
                if not original.is_relative_to(images_dir):
                    raise ValueError("Referenced image escapes the source image directory.")
                data = original.read_bytes()
                if original.suffix.lower() != ".jpg" or not data.startswith(b"\xff\xd8\xff"):
                    raise ValueError("Expected an original JPEG image.")
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)

            files = {}
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    data = path.read_bytes()
                    files[path.relative_to(staging).as_posix()] = {
                        "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                    }
            manifest = {
                "schema_version": 1,
                "snapshot_date": snapshot_date,
                "source_version": source_version,
                "source": "Original fields from the current SignTrace dictionary",
                "included_columns": {"signs": list(SIGN_COLUMNS), "meanings": list(MEANING_COLUMNS)},
                "excluded_content": ["llm_description", "llm_struct", "visual_* tables", "model outputs and query records"],
                "counts": {"signs": len(signs), "meanings": len(meanings), "images": len(image_paths)},
                "original_rows_sha256": {"signs": row_digest(signs), "meanings": row_digest(meanings)},
                "files": files,
            }
            (staging / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )
            staging.rename(output)
    return manifest["counts"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", required=True, type=Path)
    parser.add_argument("--images-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--snapshot-date", required=True, help="YYYY-MM-DD, date of the source snapshot")
    parser.add_argument("--source-version", required=True, help="Version label of the source dictionary")
    args = parser.parse_args()
    print(json.dumps(export(args.source_db, args.images_dir, args.output, args.snapshot_date, args.source_version)))


if __name__ == "__main__":
    main()
