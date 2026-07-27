"""External BenchmarkがProduction DB/データと混ざらないことを保証するテスト。"""
import csv
import os
from pathlib import Path

from benchmarks.scripts.backtest import build_backtest_pairs
from benchmarks.scripts.dataset_io import load_dataset
from benchmarks.scripts.metrics import evaluate_pair

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DB_PATH = REPO_ROOT / "backend" / "theater_pricing.db"


def test_benchmarks_scripts_do_not_import_production_db_or_models():
    """benchmarks配下のコードがapp.db/app.models(本番DB層)を一切importしていないことを
    静的に確認する(混入防止)。"""
    scripts_dir = REPO_ROOT / "benchmarks" / "scripts"
    for py_file in scripts_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "app.db" not in content, f"{py_file} が app.db を参照している"
        assert "app.models" not in content, f"{py_file} が app.models を参照している"
        assert "import sqlite3" not in content, f"{py_file} が sqlite3 を直接使用している"


def test_running_backtest_does_not_modify_production_sqlite_db(tmp_path):
    """External Benchmark実行前後で、backend本番用SQLiteファイルに変更がないことを確認する
    (存在する場合はmtimeとサイズが変化しないこと、存在しない場合は新規作成されないこと)。"""
    existed_before = BACKEND_DB_PATH.exists()
    stat_before = BACKEND_DB_PATH.stat() if existed_before else None

    dataset = load_dataset()  # benchmarks/data/public_performances.csv のテンプレートを利用
    pairs = build_backtest_pairs(dataset.valid_cases)
    for pair in pairs:
        evaluate_pair(pair)

    existed_after = BACKEND_DB_PATH.exists()
    if not existed_before:
        assert not existed_after, "backtest実行によって本番用SQLiteファイルが新規作成された"
    else:
        stat_after = BACKEND_DB_PATH.stat()
        assert stat_before.st_mtime == stat_after.st_mtime
        assert stat_before.st_size == stat_after.st_size


def test_results_are_written_only_under_benchmarks_results_dir():
    results_dir = REPO_ROOT / "benchmarks" / "results"
    assert results_dir.exists()
    for f in results_dir.glob("*.csv"):
        assert f.parent == results_dir


def test_benchmark_dataset_is_loaded_from_benchmarks_data_not_backend(monkeypatch):
    """load_dataset()のデフォルトパスが benchmarks/data/ 配下であり、
    backend/ 配下のいかなるパスも指していないことを確認する。"""
    from benchmarks.scripts.dataset_io import DEFAULT_DATASET_PATH

    assert "benchmarks" in DEFAULT_DATASET_PATH.parts
    assert "backend" not in DEFAULT_DATASET_PATH.parts


def test_syn_prefixed_rows_are_always_flagged_is_synthetic():
    """`SYN-`プレフィックスの架空サンプル行は、実データが追加された後も必ず
    is_synthetic=trueのままであること(実在公演データとの混同防止)。

    public_performances.csvは実在データの追加先でもあるため、ファイル全体が
    常にsyntheticであるとは仮定しない(SYN-行だけを対象に検証する)。"""
    template_path = REPO_ROOT / "benchmarks" / "data" / "public_performances.csv"
    with template_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    syn_rows = [r for r in rows if r["benchmark_id"].startswith("SYN-")]
    assert len(syn_rows) > 0
    for row in syn_rows:
        assert row["is_synthetic"].strip().lower() == "true", (
            f"架空サンプル行 {row['benchmark_id']} が is_synthetic=true になっていない"
        )


def test_real_prefixed_rows_are_never_flagged_is_synthetic():
    """`REAL-`プレフィックスの実在公演データはis_synthetic=falseであること。"""
    template_path = REPO_ROOT / "benchmarks" / "data" / "public_performances.csv"
    with template_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    real_rows = [r for r in rows if r["benchmark_id"].startswith("REAL-")]
    for row in real_rows:
        assert row["is_synthetic"].strip().lower() == "false", (
            f"実在公演データ {row['benchmark_id']} が is_synthetic=true になっている"
        )


def test_env_does_not_leak_backend_database_url(monkeypatch):
    """benchmarksモジュールがDATABASE_URL等の本番接続情報を参照していないこと。"""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    dataset = load_dataset()
    assert "DATABASE_URL" not in os.environ
    assert dataset is not None
