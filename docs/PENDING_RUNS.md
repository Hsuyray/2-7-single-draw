# 待執行清單(筆電)

雲端 session 寫好程式、但需要在筆電上跑的東西，依順序列在這裡。跑完一項就刪掉那一項，並把結果檔 commit 進去。

最後更新:day75。

## 1. C1 重訓:`hu_d5_full_bucket_s20_e70s` 到 8k(約 4.5–5 小時，峰值約 3.3 GB)

和 `hu_d5_full_bucket_s20_e70` 只差一個變數:`--average-mode simple`(day75 採用)。Linear CFR 沒有採用(`docs/proposals/CFR-linear-weighting.md` 第 7 節),所以 iteration weighting 維持 uniform。manifest 項目已經在雲端加好，並用 3 次迭代試跑過。

```powershell
git pull origin claude/lucid-ritchie-myhksz
python -m pytest tests -q
python -m scripts.solve_library train hu_d5_full_bucket_s20_e70s --until 8000
```

- 測試約 3–5 分鐘;有失敗就先不要訓練，把輸出貼給我。
- 參考時間:e70 的 8k 在筆電上是 16,341 秒(約 4.5 小時)、峰值 3.26 GB。
- 要中途停止(Ctrl+C)或被中斷的話，再跑一次同一行 `train` 就會從最後存的狀態續跑(每個 batch 存一次狀態)。
- 跑完後把下面這些 commit 並 push(checkpoint 本身不進 git):

```powershell
python -m scripts.solve_library status
git add solutions/manifest.json
git commit -m "day76: C1 e70s 8k trained"
git push origin claude/lucid-ritchie-myhksz
```

評估(A2,約 3 小時)等訓練完再說，不用接著跑。

## 2. 可以跑(選擇性)

| 指令 | 時間 / 記憶體 | 目的 |
|---|---|---|
| `python -m product.api.app --checkpoint checkpoints/production_v1.chk.gz --solution v1 --iterations 20000`,然後開 http://127.0.0.1:8000/docs | 載入約 30 秒 / 2 GB | 親手試 D1 的 API(Ctrl+C 結束) |

## 3. 需要你決定 / 審核的(不用跑)

- **D3**:`docs/HAND_TAXONOMY.md` 第 6 節(v1 方向)。
- **D1**:`docs/API.md` 第 10 節(第一階段已實作)。
