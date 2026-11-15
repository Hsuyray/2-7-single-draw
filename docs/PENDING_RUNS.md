# 待執行清單(筆電)

雲端 session 寫好程式、但需要在筆電上跑的東西，依順序列在這裡。跑完一項就刪掉那一項，並把結果檔 commit 進去。

最後更新:day68。

## 0. 每次先跑

```powershell
git pull origin claude/lucid-ritchie-myhksz
python -m pytest tests -q
```
預期:**910 passed**(day68 在雲端的結果)。有失敗先停下來回報。

## 1. C1 第 4 步：第一份解的 16k / 32k(依序，不能顛倒)

| # | 指令 | 時間 / 記憶體 | 產出 |
|---|---|---|---|
| 1 | `python -m scripts.solve_library evaluate hu_d5_full_bucket_s20 16000` | 約 3 小時 / 8 GB | `solutions/hu_d5_full_bucket_s20/eval/strategy_016000__b50a8627__standard__s2027.json`,manifest 更新 |
| 2 | `python -m scripts.inspect_state_convergence solutions/hu_d5_full_bucket_s20/training.state.gz --report solutions/hu_d5_full_bucket_s20/eval/strategy_016000__b50a8627__standard__s2027.json` | [推測] 5–10 分鐘 / 約 2–4 GB | `.../eval/convergence__016000__s2027.json`;最後應印 `REPORT CHECK OK` |
| 3 | `python -m scripts.solve_library train hu_d5_full_bucket_s20 --until 32000` | [推測] 約 9 小時 / 峰值 4.5–5 GB | `strategy_032000.chk.gz`(不進 git)、manifest 更新 |
| 4 | `python -m scripts.inspect_state_convergence solutions/hu_d5_full_bucket_s20/training.state.gz` | [推測] 5–10 分鐘 | `.../eval/convergence__032000__s2027.json` |
| 5 | `python -m scripts.solve_library evaluate hu_d5_full_bucket_s20 32000` | 約 3 小時以上 / 8 GB | 32k 的 standard 報告，manifest 更新 |

注意:
- **第 2 項一定要在第 3 項之前**:狀態檔只保留最新一份，訓練到 32k 會覆蓋 16k 的狀態。第 4 項要在任何更多訓練之前。
- 評估和訓練不能同時跑(記憶體)。
- 8k 不用評估(策略和 v2 完全相同，用 v2 的報告)。
- 跑完 commit:`solutions/manifest.json`、`solutions/hu_d5_full_bucket_s20/eval/`。
- 細節:`docs/C1_DESIGN.md` 8.10–8.11。

## 2. 不需要跑、但需要你審核的

- **D3 手牌分類草案 v0**:你 day67 看過;`docs/HAND_TAXONOMY.md` 第 5 節的 6 個待決問題暫用預設值，要改再說。
- **D1 API 草案 v0.2**:`docs/API.md` 第 9 節;還差 HTTP 框架與「node lock」的意思兩個確認。實作後會有一項筆電上的建置(SQLite,約 8 GB),到時再加進第 1 節。
