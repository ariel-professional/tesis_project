from __future__ import annotations

from pathlib import Path

import pytest

from tesis_domain_extensions.domains.single_row_facility_layout.fast_result_store import (
    FastResultReader,
    FastResultStoreError,
    FastResultWriter,
)


def _ids(ordinal: int) -> tuple[str, str]:
    return f"{ordinal + 1:064x}", f"{(ordinal % 7) + 1000:064x}"


def _completed_store(tmp_path: Path, count: int = 123):
    workspace = tmp_path.resolve()
    run_directory = workspace / "domain_runs" / "12345678-1234-4234-8234-123456789abc"
    with FastResultWriter(run_directory) as writer:
        case_ids = []
        for ordinal in range(count):
            case_id, forest_id = _ids(ordinal)
            case_ids.append(case_id)
            writer.append_case(
                {
                    "case_id": case_id,
                    "forest_id": forest_id,
                    "value": ordinal,
                }
            )
        writer.write_ordinal_index("orders/order-1.u64", range(count))
        writer.write_sorted_ordinal_index(
            "orders/order-2.u64", (((ordinal % 4,), ordinal) for ordinal in range(count))
        )
        writer.write_ordinal_index("frontier/design-1.u64", range(0, count, 3))
        manifest = writer.finalize()
    return workspace, run_directory, manifest, case_ids


def test_writer_and_reader_support_far_pages_details_and_equivalent_forests(
    tmp_path: Path,
) -> None:
    workspace, run_directory, manifest, case_ids = _completed_store(tmp_path)
    reader = FastResultReader(workspace, run_directory, manifest, completed=True)
    try:
        page = reader.page("orders/order-1.u64", 2)
        assert [item["value"] for item in page] == list(range(100, 123))
        expected_order = sorted(range(123), key=lambda ordinal: (ordinal % 4, ordinal))
        sorted_page = reader.page("orders/order-2.u64", 2)
        assert [item["value"] for item in sorted_page] == expected_order[100:150]
        assert reader.find_case(case_ids[75])["value"] == 75
        equivalents = list(reader.iter_equivalent_cases(_ids(0)[1]))
        assert [item["value"] for item in equivalents] == list(range(0, 123, 7))
        equivalent_count, equivalent_page = reader.equivalent_page(_ids(0)[1], 2, limit=3)
        assert equivalent_count == 18
        assert [item["value"] for item in equivalent_page] == [14, 21, 28]
        assert [item["value"] for item in reader.page("frontier/design-1.u64", 0)] == list(
            range(0, 123, 3)
        )
    finally:
        reader.close()


def test_reader_rejects_unconfirmed_run_and_hash_mismatch(tmp_path: Path) -> None:
    workspace, run_directory, manifest, _ = _completed_store(tmp_path, count=2)
    with pytest.raises(FastResultStoreError, match="completed"):
        FastResultReader(workspace, run_directory, manifest, completed=False)

    manifest["cases.ndjson"]["sha256"] = "0" * 64
    with pytest.raises(FastResultStoreError, match="hash"):
        FastResultReader(workspace, run_directory, manifest, completed=True)


def test_reader_rejects_unbounded_page_size(tmp_path: Path) -> None:
    workspace, run_directory, manifest, _ = _completed_store(tmp_path, count=2)
    reader = FastResultReader(workspace, run_directory, manifest, completed=True)
    try:
        with pytest.raises(ValueError, match="between 1 and 50"):
            reader.page("orders/order-1.u64", 0, page_size=51)
    finally:
        reader.close()


def test_writer_rejects_non_hex_ids_and_indexes_outside_fixed_folders(tmp_path: Path) -> None:
    run_directory = tmp_path / "domain_runs" / "12345678-1234-4234-8234-123456789abc"
    with FastResultWriter(run_directory) as writer:
        with pytest.raises(FastResultStoreError, match="case_id"):
            writer.append_case({"case_id": "bad", "forest_id": "a" * 64})
        with pytest.raises(FastResultStoreError, match="orders"):
            writer.write_ordinal_index("other/index.u64", [])
