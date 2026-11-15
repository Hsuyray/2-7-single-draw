# 待執行清單(筆電)

雲端 session 寫好程式、但需要在筆電上跑的東西，依順序列在這裡。跑完一項就刪掉那一項，並把結果檔 commit 進去。

最後更新:day70。

## 0. 每次先跑

```powershell
git pull origin claude/lucid-ritchie-myhksz
python -m pip install -r requirements.txt
python -m pytest tests -q
```
預期:**928 passed**(day70 在雲端的結果;day69 那個 xfail 已因引擎修正變成一般的回歸測試)。有其他失敗先停下來回報。

## 1. C1:用修正後的引擎從 0 訓練(day70)

引擎的 all-in 規則已修正(`docs/proposals/ENGINE-all-in-round.md` 第 7 節)。舊的 `hu_d5_full_bucket_s20` 是舊規則的解，**不要再訓練或評估它**;新解 `hu_d5_full_bucket_s20_e70` 已加進 `solutions/manifest.json`(同樣的設定:籌碼 20、`max_draw=5`、bucket、`full`、seed 42,milestones 8k / 16k / 32k)。

依序跑:

```powershell
python -m scripts.solve_library train hu_d5_full_bucket_s20_e70 --until 8000
python -m scripts.inspect_state_convergence solutions/hu_d5_full_bucket_s20_e70/training.state.gz
python -m scripts.solve_library evaluate hu_d5_full_bucket_s20_e70 8000
python -m scripts.solve_library status hu_d5_full_bucket_s20_e70
```

- 第 1 行 [推測]:約 5–8 小時(舊規則 8k 是 7.5 小時，但當時筆電偏慢;每次迭代時間沒變，節點多約 20%)。峰值記憶體約 3.5 GB。中斷的話用同一行指令續跑。
- 第 2 行一定要在**繼續訓練之前**跑(狀態檔只保留最新一份)。約 5–10 分鐘。
- 第 3 行 [推測]:約 3–4 小時、9–10 GB(v2 是 3.1 小時、8.1 GB,節點更多)。訓練和評估不能同時跑。
- 跑完 commit `solutions/manifest.json` 和 `solutions/hu_d5_full_bucket_s20_e70/eval/`,並把第 2 行的輸出貼給我。checkpoint 和狀態檔不要 commit(太大)。
- 16k / 32k 等 8k 的結果出來再決定(依 `docs/C1_DESIGN.md` 8.6 的停止規則)。

## 2. 可以跑(選擇性)

| 指令 | 時間 / 記憶體 | 目的 |
|---|---|---|
| `python -m product.api.app --checkpoint checkpoints/production_v1.chk.gz --solution v1 --iterations 20000`,然後開 http://127.0.0.1:8000/docs | 載入約 30 秒 / 2 GB | 親手試 D1 的 API(Ctrl+C 結束) |

## 3. 需要你決定 / 審核的(不用跑)

- **D3**:`docs/HAND_TAXONOMY.md` 第 6 節(v1 方向)。
- **D1**:`docs/API.md` 第 10 節(第一階段已實作)。
