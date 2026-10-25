"""Brainscape flashcards: 2-column CSVs (question, answer), no header, split into fixed-size batches."""

import csv
import re
from pathlib import Path

BATCH_NAME = re.compile(r"^batch-(\d+)\.csv$")


class CardStore:
    def __init__(self, data_dir: Path, batch_size: int = 200):
        self.dir = data_dir
        self.batch_size = batch_size
        self.batches_dir = data_dir / "batches"
        self.uploaded_dir = data_dir / "uploaded"
        self.seen_file = data_dir / "seen.txt"

    @staticmethod
    def key(front: str) -> str:
        return " ".join(front.split()).casefold()

    def _seen(self) -> set[str]:
        if not self.seen_file.exists():
            return set()
        return set(self.seen_file.read_text(encoding="utf-8").splitlines())

    @staticmethod
    def count(path: Path) -> int:
        with path.open(encoding="utf-8", newline="") as f:
            return sum(1 for _ in csv.reader(f))

    @staticmethod
    def _numbered(folder: Path) -> list[tuple[int, Path]]:
        if not folder.exists():
            return []
        found = ((BATCH_NAME.match(p.name), p) for p in folder.iterdir())
        return sorted((int(m.group(1)), p) for m, p in found if m)

    def batches(self) -> list[tuple[Path, int]]:
        """Batches not yet uploaded, oldest first, with their card counts."""
        return [(p, self.count(p)) for _, p in self._numbered(self.batches_dir)]

    def _current_batch(self) -> Path:
        pending = self._numbered(self.batches_dir)
        if pending and self.count(pending[-1][1]) < self.batch_size:
            return pending[-1][1]
        used = [n for n, _ in pending + self._numbered(self.uploaded_dir)]
        return self.batches_dir / f"batch-{max(used, default=0) + 1:03d}.csv"

    def add(self, front: str, back: str) -> bool:
        """Append a card to the batch being filled. Returns False if this front was saved before."""
        key = self.key(front)
        if key in self._seen():
            return False
        self.batches_dir.mkdir(parents=True, exist_ok=True)
        with self._current_batch().open("a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([_clean(front), _clean(back)])
        with self.seen_file.open("a", encoding="utf-8") as f:
            f.write(key + "\n")
        return True

    def mark_oldest_uploaded(self) -> Path | None:
        """Move the oldest pending batch into uploaded/. Returns its new path."""
        pending = self.batches()
        if not pending:
            return None
        self.uploaded_dir.mkdir(parents=True, exist_ok=True)
        oldest = pending[0][0]
        return oldest.rename(self.uploaded_dir / oldest.name)


def _clean(text: str) -> str:
    return text.replace("<", "").replace(">", "").strip()
