# 待執行清單(筆電)

雲端 session 寫好程式、但需要在筆電上跑的東西，依順序列在這裡。跑完一項就刪掉那一項，並把結果檔 commit 進去。

最後更新:day75。

目前沒有長時間的訓練要跑(day74:使用者暫停長時間訓練，先改邏輯)。C1 下一次重訓要等 Linear CFR 的實驗有結論(`docs/proposals/CFR-average-weighting.md` 第 9 節)。

## 1. 有空時跑一次測試(約 3–5 分鐘)

day75 加了 `--average-mode`(simple averaging)。預設行為沒變，雲端已經跑過全部測試;這裡只是在 Windows / Python 3.12 上再確認一次。

```powershell
git pull origin claude/lucid-ritchie-myhksz
python -m pytest tests -q
```

全部通過就好，不用 commit 任何東西。有失敗的話把輸出貼給我。

## 2. 可以跑(選擇性)

| 指令 | 時間 / 記憶體 | 目的 |
|---|---|---|
| `python -m product.api.app --checkpoint checkpoints/production_v1.chk.gz --solution v1 --iterations 20000`,然後開 http://127.0.0.1:8000/docs | 載入約 30 秒 / 2 GB | 親手試 D1 的 API(Ctrl+C 結束) |

## 3. 需要你決定 / 審核的(不用跑)

- **D3**:`docs/HAND_TAXONOMY.md` 第 6 節(v1 方向)。
- **D1**:`docs/API.md` 第 10 節(第一階段已實作)。
