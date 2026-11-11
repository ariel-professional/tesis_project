from __future__ import annotations

import hashlib
import heapq
import json
import os
import pickle
import re
import struct
from collections.abc import Iterable, Iterator, Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

_U64 = struct.Struct("<Q")
_INDEX_RECORD = struct.Struct("<64sQ")
_HEX_ID = re.compile(r"^[0-9a-f]{64}$")
_SORT_BLOCK_SIZE = 50_000
_PAGE_SIZE = 50


class FastResultStoreError(RuntimeError):
    """Fast result files could not be safely written or read."""


def _fsync_file(file: Any) -> None:
    file.flush()
    os.fsync(file.fileno())


def _write_u64(file: Any, value: int) -> None:
    if type(value) is not int or not 0 <= value < 2**64:
        raise FastResultStoreError("ordinal or offset does not fit in unsigned 64 bits")
    file.write(_U64.pack(value))


class FastResultWriter:
    """Sequential case writer with fixed-width offsets and ID lookup indexes."""

    def __init__(self, run_directory: Path) -> None:
        self.run_directory = run_directory
        self.run_directory.parent.mkdir(parents=True, exist_ok=True)
        if self.run_directory.parent.is_symlink() or not self.run_directory.parent.is_dir():
            raise FastResultStoreError("domain runs directory must be real")
        self.run_directory.mkdir(exist_ok=True)
        if self.run_directory.is_symlink() or not self.run_directory.is_dir():
            raise FastResultStoreError("fast result run directory must be a real directory")
        self.run_directory = self.run_directory.resolve(strict=True)
        self._cases_path = self.run_directory / "cases.ndjson.tmp"
        self._offsets_path = self.run_directory / "offsets.u64.tmp"
        self._case_pairs_path = self.run_directory / "by-case-id.unsorted.tmp"
        self._forest_pairs_path = self.run_directory / "by-forest-id.unsorted.tmp"
        self._cases = self._cases_path.open("xb")
        self._offsets = self._offsets_path.open("xb")
        self._case_pairs = self._case_pairs_path.open("xb")
        self._forest_pairs = self._forest_pairs_path.open("xb")
        self.case_count = 0
        self._finalized = False
        self._ordinal_indexes: set[str] = set()

    def __enter__(self) -> FastResultWriter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def append_case(self, case: Mapping[str, object]) -> int:
        self._ensure_open()
        case_id = case.get("case_id")
        forest_id = case.get("forest_id")
        if not isinstance(case_id, str) or _HEX_ID.fullmatch(case_id) is None:
            raise FastResultStoreError("case_id must be a 64-character lower-case hexadecimal ID")
        if not isinstance(forest_id, str) or _HEX_ID.fullmatch(forest_id) is None:
            raise FastResultStoreError("forest_id must be a 64-character lower-case hexadecimal ID")
        ordinal = self.case_count
        start = self._cases.tell()
        payload = (
            json.dumps(
                dict(case), ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            + b"\n"
        )
        end = start + len(payload)
        if end >= 2**64:
            raise FastResultStoreError("case file offset exceeds unsigned 64-bit range")
        _write_u64(self._offsets, start)
        self._cases.write(payload)
        self._case_pairs.write(_INDEX_RECORD.pack(case_id.encode("ascii"), ordinal))
        self._forest_pairs.write(_INDEX_RECORD.pack(forest_id.encode("ascii"), ordinal))
        self.case_count += 1
        return ordinal

    def write_ordinal_index(self, relative_path: str, ordinals: Iterable[int]) -> None:
        self._ensure_open()
        destination = self._safe_child(relative_path)
        if not (
            destination.relative_to(self.run_directory).parts[0] in {"orders", "frontier"}
            and destination.suffix == ".u64"
        ):
            raise FastResultStoreError("ordinal indexes must be orders/*.u64 or frontier/*.u64")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._verify_index_parent(destination)
        temporary = destination.with_name(destination.name + ".tmp")
        with temporary.open("xb") as file:
            for ordinal in ordinals:
                if ordinal >= self.case_count:
                    raise FastResultStoreError("ordinal index references an unknown case")
                _write_u64(file, ordinal)
            _fsync_file(file)
        self._publish(temporary, destination)
        self._ordinal_indexes.add(relative_path.replace("\\", "/"))

    def write_sorted_ordinal_index(
        self,
        relative_path: str,
        keyed_ordinals: Iterable[tuple[tuple[Any, ...], int]],
    ) -> None:
        self._ensure_open()
        destination = self._safe_child(relative_path)
        if not (
            destination.relative_to(self.run_directory).parts[0] == "orders"
            and destination.suffix == ".u64"
        ):
            raise FastResultStoreError("sorted order indexes must be orders/*.u64")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._verify_index_parent(destination)
        runs: list[Path] = []
        block: list[tuple[tuple[Any, ...], int]] = []
        for key, ordinal in keyed_ordinals:
            if type(ordinal) is not int or not 0 <= ordinal < self.case_count:
                raise FastResultStoreError("order index references an unknown case")
            block.append((key, ordinal))
            if len(block) == _SORT_BLOCK_SIZE:
                runs.append(self._write_order_run(relative_path, len(runs), block))
                block = []
        if block:
            runs.append(self._write_order_run(relative_path, len(runs), block))
        temporary = destination.with_name(destination.name + ".tmp")
        streams = [path.open("rb") for path in runs]
        with temporary.open("xb") as output:
            iterators = [self._read_order_run(stream) for stream in streams]
            for _, ordinal in heapq.merge(*iterators, key=lambda item: (item[0], item[1])):
                _write_u64(output, ordinal)
            _fsync_file(output)
        for stream in streams:
            stream.close()
        for path in runs:
            path.unlink()
        self._publish(temporary, destination)
        self._ordinal_indexes.add(relative_path.replace("\\", "/"))

    def iter_appended_cases(self) -> Iterator[tuple[int, dict[str, Any]]]:
        """Stream rows already appended without retaining the collection in memory."""

        self._ensure_open()
        self._cases.flush()
        with self._cases_path.open("rb") as file:
            for ordinal, raw in enumerate(file):
                try:
                    value = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise FastResultStoreError("appended case is invalid JSON") from exc
                if not isinstance(value, dict):
                    raise FastResultStoreError("appended case must be a JSON object")
                yield ordinal, value

    @staticmethod
    def exact_fraction(case: Mapping[str, Any], objective_id: str) -> Fraction | None:
        vector = case.get("criteria_vector")
        if not isinstance(vector, dict):
            return None
        value = vector.get(objective_id)
        if not isinstance(value, dict):
            return None
        numerator, denominator = value.get("numerator"), value.get("denominator")
        if type(numerator) is not int or type(denominator) is not int or denominator <= 0:
            return None
        return Fraction(numerator, denominator)

    def finalize(self) -> dict[str, dict[str, int | str]]:
        self._ensure_open()
        end = self._cases.tell()
        _write_u64(self._offsets, end)
        for file in (self._cases, self._offsets, self._case_pairs, self._forest_pairs):
            _fsync_file(file)
            file.close()
        self._sort_id_pairs(self._case_pairs_path, "by-case-id.idx")
        self._sort_id_pairs(self._forest_pairs_path, "by-forest-id.idx")
        self._publish(self._cases_path, self.run_directory / "cases.ndjson")
        self._publish(self._offsets_path, self.run_directory / "offsets.u64")
        self._case_pairs_path.unlink()
        self._forest_pairs_path.unlink()
        self._finalized = True
        names = [
            "cases.ndjson",
            "offsets.u64",
            "by-case-id.idx",
            "by-forest-id.idx",
            *sorted(self._ordinal_indexes),
        ]
        return {name: self._file_digest(self._safe_child(name)) for name in names}

    def close(self) -> None:
        for file in (self._cases, self._offsets, self._case_pairs, self._forest_pairs):
            if not file.closed:
                file.close()

    def _sort_id_pairs(self, source: Path, destination_name: str) -> None:
        runs: list[Path] = []
        with source.open("rb") as file:
            while records := file.read(_INDEX_RECORD.size * _SORT_BLOCK_SIZE):
                if len(records) % _INDEX_RECORD.size != 0:
                    raise FastResultStoreError("ID index spool has a truncated record")
                values = [
                    _INDEX_RECORD.unpack_from(records, offset)
                    for offset in range(0, len(records), _INDEX_RECORD.size)
                ]
                values.sort(key=lambda item: (item[0], item[1]))
                run_path = self.run_directory / f".{destination_name}.{len(runs)}.tmp"
                with run_path.open("xb") as run:
                    for value in values:
                        run.write(_INDEX_RECORD.pack(*value))
                runs.append(run_path)
        destination = self.run_directory / destination_name
        temporary = destination.with_name(destination.name + ".tmp")
        iterators = [self._read_index_records(path) for path in runs]
        with temporary.open("xb") as output:
            for identifier, ordinal in heapq.merge(*iterators, key=lambda pair: pair):
                output.write(_INDEX_RECORD.pack(identifier, ordinal))
            _fsync_file(output)
        self._publish(temporary, destination)
        for path in runs:
            path.unlink()

    def _write_order_run(
        self,
        relative_path: str,
        run_number: int,
        values: list[tuple[tuple[Any, ...], int]],
    ) -> Path:
        values.sort(key=lambda item: (item[0], item[1]))
        name = Path(relative_path).name
        run_path = self.run_directory / f".{name}.{run_number}.run.tmp"
        with run_path.open("xb") as run:
            for value in values:
                pickle.dump(value, run, protocol=pickle.HIGHEST_PROTOCOL)
        return run_path

    @staticmethod
    def _read_order_run(file: Any) -> Iterator[tuple[tuple[Any, ...], int]]:
        while True:
            try:
                value = pickle.load(file)
            except EOFError:
                return
            if (
                not isinstance(value, tuple)
                or len(value) != 2
                or not isinstance(value[0], tuple)
                or type(value[1]) is not int
            ):
                raise FastResultStoreError("temporary order run contains an invalid record")
            yield value

    @staticmethod
    def _read_index_records(path: Path) -> Iterator[tuple[bytes, int]]:
        with path.open("rb") as file:
            while raw := file.read(_INDEX_RECORD.size):
                if len(raw) != _INDEX_RECORD.size:
                    raise FastResultStoreError("sorted ID index has a truncated record")
                yield _INDEX_RECORD.unpack(raw)

    def _safe_child(self, relative_path: str) -> Path:
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts or path.name in {"", "."}:
            raise FastResultStoreError("index path must stay inside the run directory")
        result = self.run_directory / path
        try:
            result.parent.resolve().relative_to(self.run_directory)
        except (OSError, ValueError) as exc:
            raise FastResultStoreError("index path escapes the run directory") from exc
        return result

    def _verify_index_parent(self, destination: Path) -> None:
        if destination.parent.is_symlink() or not destination.parent.is_dir():
            raise FastResultStoreError("index directory must be real")
        try:
            destination.parent.resolve(strict=True).relative_to(self.run_directory)
        except (OSError, ValueError) as exc:
            raise FastResultStoreError("index directory escapes the run directory") from exc

    @staticmethod
    def _file_digest(path: Path) -> dict[str, int | str]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as file:
            while chunk := file.read(1024 * 1024):
                size += len(chunk)
                digest.update(chunk)
        return {"size": size, "sha256": digest.hexdigest()}

    @staticmethod
    def _publish(temporary: Path, destination: Path) -> None:
        os.replace(temporary, destination)

    def _ensure_open(self) -> None:
        if self._finalized or self._cases.closed:
            raise FastResultStoreError("fast result writer is already finalized")


class FastResultReader:
    """Verified random-access reader for a completed fast result bundle."""

    def __init__(
        self,
        workspace: Path,
        run_directory: Path,
        file_manifest: Mapping[str, Mapping[str, object]],
        *,
        completed: bool,
    ) -> None:
        if not completed:
            raise FastResultStoreError("only completed fast runs can be opened")
        self.workspace = workspace.resolve(strict=True)
        self.run_directory = run_directory.resolve(strict=True)
        try:
            self.run_directory.relative_to(self.workspace)
        except ValueError as exc:
            raise FastResultStoreError("run directory escapes the workspace") from exc
        if run_directory.is_symlink() or not self.run_directory.is_dir():
            raise FastResultStoreError("run directory must be a real directory")
        if run_directory.parent.is_symlink():
            raise FastResultStoreError("domain runs directory must be real")
        self._files: dict[str, Any] = {}
        self._identities: dict[str, tuple[int, int, int, int]] = {}
        self._confirmed_names = set(file_manifest)
        try:
            required = {"cases.ndjson", "offsets.u64", "by-case-id.idx", "by-forest-id.idx"}
            if not required <= set(file_manifest):
                raise FastResultStoreError("confirmed metadata is missing required result files")
            for name, expected in file_manifest.items():
                self._open_confirmed_file(name, expected)
            offsets_size = self._identities["offsets.u64"][2]
            if offsets_size % _U64.size != 0:
                raise FastResultStoreError("offset index has a partial entry")
            self.case_count = offsets_size // _U64.size - 1
            self._validate_index_sizes()
        except Exception:
            self.close()
            raise

    def _open_confirmed_file(self, name: str, expected: Mapping[str, object]) -> None:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise FastResultStoreError("confirmed file reference escapes the run")
        raw_path = self.run_directory / relative
        if raw_path.is_symlink() or not raw_path.is_file():
            raise FastResultStoreError(f"{name} must be a regular file")
        resolved = raw_path.resolve(strict=True)
        try:
            resolved.relative_to(self.run_directory)
        except ValueError as exc:
            raise FastResultStoreError("confirmed file escapes the run directory") from exc
        identity = self._identity(resolved.stat())
        if expected.get("size") != identity[2]:
            raise FastResultStoreError(f"{name} size does not match confirmed metadata")
        if expected.get("sha256") != self._digest(resolved):
            raise FastResultStoreError(f"{name} hash does not match confirmed metadata")
        file = resolved.open("rb")
        self._files[name] = file
        self._identities[name] = self._identity(os.fstat(file.fileno()))

    def get_case(self, ordinal: int) -> dict[str, Any]:
        if type(ordinal) is not int or not 0 <= ordinal < self.case_count:
            raise IndexError("case ordinal is outside the result")
        start = self._read_offset(ordinal)
        end = self._read_offset(ordinal + 1)
        file = self._verified_file("cases.ndjson")
        file.seek(start)
        raw = file.read(end - start)
        if not raw.endswith(b"\n"):
            raise FastResultStoreError("case line is incomplete")
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FastResultStoreError("case line is invalid JSON") from exc
        if not isinstance(value, dict):
            raise FastResultStoreError("case line must be an object")
        return value

    def __enter__(self) -> FastResultReader:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def page(
        self,
        order_path: str,
        page: int,
        *,
        page_size: int = 50,
        reverse: bool = False,
    ) -> list[dict[str, Any]]:
        if (
            type(page) is not int
            or page < 0
            or type(page_size) is not int
            or not 1 <= page_size <= _PAGE_SIZE
        ):
            raise ValueError("page must be non-negative and page size must be between 1 and 50")
        index = self._verified_file(order_path)
        count = self.index_count(order_path)
        start = page * page_size
        end = min(count, start + page_size)
        if start >= end:
            return []
        if reverse:
            ordinals = []
            for position in range(end - 1, start - 1, -1):
                index.seek(position * _U64.size)
                raw = index.read(_U64.size)
                if len(raw) != _U64.size:
                    raise FastResultStoreError("ordinal order index has a partial entry")
                ordinals.append(_U64.unpack(raw)[0])
        else:
            index.seek(start * _U64.size)
            selected = index.read((end - start) * _U64.size)
            if len(selected) != (end - start) * _U64.size:
                raise FastResultStoreError("ordinal order index has a partial entry")
            ordinals = [
                _U64.unpack_from(selected, offset)[0]
                for offset in range(0, len(selected), _U64.size)
            ]
        if any(ordinal >= self.case_count for ordinal in ordinals):
            raise FastResultStoreError("ordinal order index has a partial entry")
        return [self.get_case(ordinal) for ordinal in ordinals]

    def index_count(self, index_path: str) -> int:
        index = self._verified_file(index_path)
        size = self._identities[index_path][2]
        if size % _U64.size:
            raise FastResultStoreError("ordinal index has a partial entry")
        del index
        return size // _U64.size

    def find_case(self, case_id: str) -> dict[str, Any]:
        ordinal = self._find_first("by-case-id.idx", case_id)
        if ordinal is None:
            raise KeyError(case_id)
        return self.get_case(ordinal)

    def iter_equivalent_cases(self, forest_id: str) -> Iterator[dict[str, Any]]:
        for ordinal in self._find_all("by-forest-id.idx", forest_id):
            yield self.get_case(ordinal)

    def equivalent_page(
        self, forest_id: str, offset: int, limit: int = 50
    ) -> tuple[int, list[dict[str, Any]]]:
        if (
            type(offset) is not int
            or offset < 0
            or type(limit) is not int
            or not 1 <= limit <= _PAGE_SIZE
        ):
            raise ValueError("equivalent page bounds are invalid")
        if _HEX_ID.fullmatch(forest_id) is None:
            raise ValueError("identifier must be 64 lower-case hexadecimal characters")
        name = "by-forest-id.idx"
        file = self._verified_file(name)
        count = self._identities[name][2] // _INDEX_RECORD.size
        target = forest_id.encode("ascii")

        def bound(upper: bool) -> int:
            low, high = 0, count
            while low < high:
                middle = (low + high) // 2
                file.seek(middle * _INDEX_RECORD.size)
                candidate, _ = _INDEX_RECORD.unpack(file.read(_INDEX_RECORD.size))
                if candidate < target or (upper and candidate == target):
                    low = middle + 1
                else:
                    high = middle
            return low

        first, last = bound(False), bound(True)
        start = min(first + offset, last)
        ordinals = []
        for position in range(start, min(start + limit, last)):
            file.seek(position * _INDEX_RECORD.size)
            _, ordinal = _INDEX_RECORD.unpack(file.read(_INDEX_RECORD.size))
            ordinals.append(ordinal)
        return last - first, [self.get_case(item) for item in ordinals]

    def close(self) -> None:
        for file in self._files.values():
            file.close()
        self._files.clear()

    def _find_first(self, index_name: str, identifier: str) -> int | None:
        matches = self._find_all(index_name, identifier)
        return matches[0] if matches else None

    def _find_all(self, index_name: str, identifier: str) -> list[int]:
        if _HEX_ID.fullmatch(identifier) is None:
            raise ValueError("identifier must be 64 lower-case hexadecimal characters")
        file = self._verified_file(index_name)
        count = self._identities[index_name][2] // _INDEX_RECORD.size
        target = identifier.encode("ascii")
        low, high = 0, count
        while low < high:
            middle = (low + high) // 2
            file.seek(middle * _INDEX_RECORD.size)
            candidate, _ = _INDEX_RECORD.unpack(file.read(_INDEX_RECORD.size))
            if candidate < target:
                low = middle + 1
            else:
                high = middle
        matches: list[int] = []
        while low < count:
            file.seek(low * _INDEX_RECORD.size)
            candidate, ordinal = _INDEX_RECORD.unpack(file.read(_INDEX_RECORD.size))
            if candidate != target:
                break
            matches.append(ordinal)
            low += 1
        return matches

    def _read_offset(self, ordinal: int) -> int:
        file = self._verified_file("offsets.u64")
        file.seek(ordinal * _U64.size)
        raw = file.read(_U64.size)
        if len(raw) != _U64.size:
            raise FastResultStoreError("offset index ended unexpectedly")
        return cast(int, _U64.unpack(raw)[0])

    def _verified_file(self, name: str) -> Any:
        if name not in self._confirmed_names:
            raise FastResultStoreError("file is not listed in confirmed artifact metadata")
        file = self._files.get(name)
        if file is None:
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise FastResultStoreError("file reference escapes the run directory")
            resolved = (self.run_directory / path).resolve(strict=True)
            try:
                resolved.relative_to(self.run_directory)
            except ValueError as exc:
                raise FastResultStoreError("file reference escapes the run directory") from exc
            if (self.run_directory / path).is_symlink() or not resolved.is_file():
                raise FastResultStoreError("indexed file must be a regular file")
            file = resolved.open("rb")
            self._files[name] = file
            self._identities[name] = self._identity(os.fstat(file.fileno()))
        if self._identity(os.fstat(file.fileno())) != self._identities[name]:
            raise FastResultStoreError(f"{name} changed after result opening")
        return file

    def _validate_index_sizes(self) -> None:
        cases_size = self._identities["cases.ndjson"][2]
        first = self._read_offset(0) if self.case_count else 0
        last = self._read_offset(self.case_count)
        if first != 0 or last != cases_size:
            raise FastResultStoreError("offset index does not cover the case file")
        for name in ("by-case-id.idx", "by-forest-id.idx"):
            if self._identities[name][2] != self.case_count * _INDEX_RECORD.size:
                raise FastResultStoreError(f"{name} has an unexpected record count")

    @staticmethod
    def _identity(stat: os.stat_result) -> tuple[int, int, int, int]:
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns

    @staticmethod
    def _digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            while chunk := file.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
