# benchmarks/data/imports/ — 投入済みインポートファイルのアーカイブ

このディレクトリは、`benchmarks/data/public_performances.csv` へ過去に投入した
「投入時点のファイルそのもの」を再現性・監査証跡のために保存する場所です。

**ここにあるファイルは実行時には一切読み込まれません。**
Benchmark Runner・テスト・レポート生成は常に `benchmarks/data/public_performances.csv`
のみを参照します(`benchmarks/scripts/dataset_io.py` の `DEFAULT_DATASET_PATH`)。

## なぜ残すか

`public_performances.csv` は投入後にnotesの追記・sold_out_statusの更新・
performance_countの是正等、継続的に上書き修正されます(例:
`docs/PUBLIC_BENCHMARK_REPORT.md` の更新履歴を参照)。そのため「いつ・どのファイルを・
どう投入したか」という投入時点のスナップショットは`public_performances.csv`の
git履歴だけでは追いにくくなります。ここに投入ファイルをそのまま残すことで、
後から「この行はどのバッチ由来か」を追跡できるようにしています。

## ファイル一覧

- `batch01_candidate.csv` — 初期20件(REAL-0001〜REAL-0020, SYN-0001/0002を除く)を
  `public_performances.csv` へ投入した際の候補ファイル。投入後に追加調査で
  performance_count・sold_out_status・notes等が更新されているため、本ファイルの値は
  **現行の`public_performances.csv`より古い場合がある**。現在値の参照先としては使わないこと。
- `phase2_ready_import.csv` — Phase 2で劇団チョコレートケーキ「松本公演」1件
  (`benchmark_id=P2-READY-GC-2023-MATSUMOTO`)を投入した際の投入ファイル。
  投入時に列名を `sale_start_date` → `ticket_sale_start_date`
  (`benchmarks/schema/models.py` の `BenchmarkPerformance.ticket_sale_start_date` に合わせて)
  修正済み。値そのものは投入時点から変更していない。

## 新しいバッチを投入する場合

同様の「ready importファイル」を作る場合は、列名を
`benchmarks/schema/models.py` の `BenchmarkPerformance` フィールド名(特に
`ticket_sale_start_date`)に合わせてください。投入後はこのディレクトリへ
`batchNN_*.csv` 等の名前でコピーを残すことを推奨します。
