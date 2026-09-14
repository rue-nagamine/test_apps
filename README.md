# test_apps — 会議室予約アプリ

社内ツール「テスト実施台帳」のテスト対象リポジトリ。
FastAPI + SQLite の小さな会議室予約アプリと、そのテスト項目・自動テスト結果が入っている。

台帳はこのリポジトリを **読み取り専用で clone してファイルを読むだけ**で、
テストは実行しない。そのため `reports/junit.xml` は**コミットして運用する**。

## 構成

```
.testapp.yml   台帳の読み込み設定（項目と結果の置き場所、突合ルール）
app/           アプリ本体。booking.py が業務ルールの中核
static/        画面（HTML 1枚）
tests/         pytest
testcases/     台帳が読むテスト項目（YAML）
reports/       pytest --junitxml の出力。コミットする
```

## 動かす

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8001
```

<http://localhost:8001> を開く。

8000 番は「テスト実施台帳」側が使うので、こちらは 8001 番で動かす。

## テストする

```bash
.venv/bin/pytest --junitxml=reports/junit.xml
```

**終了コードが非0になるのが正しい状態。** 台帳の表示確認のために、
失敗する自動テストとスキップする自動テストをわざと1件ずつ入れてある（下記）。
XML を更新したらコミットすること。

## 業務ルール（自動テストの対象）

| ルール | 補足 |
|---|---|
| 同一会議室で時間帯が重複する予約は作れない | 境界: 前の終了時刻 = 次の開始時刻は OK |
| 参加人数が定員を超える予約は作れない | 定員ちょうどは OK |
| 営業時間 9:00–20:00 の外は予約できない | 終了 20:00 ちょうどは OK |
| `end <= start` は不正 | 同時刻・逆転とも不可 |
| 開始1時間前を過ぎたキャンセルは不可 | |

## テスト項目

`testcases/*.yml`。手動15件・自動10件を 予約 / 会議室 / 画面 の3カテゴリに分けている。

- `id` は**結果の紐づけキー。一度決めたら絶対に変えない。**
  変えると過去の実施結果が全部はずれる。
- 自動項目は `auto_ref` に `<モジュール名>::<関数名>` を書く
  （`.testapp.yml` の `template: "{classname}::{name}"` + `strip_package: tests` に対応）。
- `TC-RSV-009` だけは `auto_ref` を書かず、テスト名に ID を埋め込んで突合させている。
  台帳は `classname` / `name` の中から ID を拾うが、`_TC_RSV_009` のように
  識別子の途中に続けて書くと単語境界が立たず拾われないので、
  pytest のパラメータ ID として付けてある
  （JUnit XML 上の name が `test_rejects_non_positive_duration[TC-RSV-009]` になる）。

## 台帳の表示確認のために仕込んであるもの

| 仕込み | 対象 |
|---|---|
| 失敗する自動テスト 1件 | `TC-RSV-010`（4時間上限。まだ未実装なので `DID NOT RAISE`） |
| スキップする自動テスト 1件 | `TC-RSV-011`（`@pytest.mark.skip(reason="仕様確認中")`） |
| 紐づかない結果 2件 | `test_rejects_cancel_after_deadline` / `test_creates_and_lists_reservations`<br>対応する項目 ID を用意していないので「紐づかなかった結果」として警告に出る |

現状: **10 passed / 1 failed / 1 skipped**、自動項目 10件すべて突合。

## 台帳に登録する

1. `~/files/testapp` で `./run.sh`
2. <http://localhost:8000> で「案件」を追加。リポジトリに
   `https://github.com/rue-nagamine/test_apps.git`、ブランチ `main`
3. 「実施サイクル」を追加し、「Git から同期」を押す

台帳は `git clone` を `PATH=/usr/bin:/bin:/usr/local/bin` の制限環境で実行するため、
**このリポジトリは public である必要がある**（Homebrew の `gh` が PATH に入らず、
private だと credential helper が見つからずに clone が失敗する）。

## 再テスト判定

台帳は項目の `title` / `steps` / `expected` / `type` からハッシュを取っている。
そのため:

- `expected` を書き換えて push → 再同期すると、結果入力済みの項目に「要再テスト」が付く
- `priority` / `category` / `tags` / `level` だけを書き換えても要再テストにはならない
