# 待執行清單(筆電)

雲端 session 寫好程式、但需要在筆電上跑的東西，依順序列在這裡。跑完一項就刪掉那一項，並把結果檔 commit 進去。

最後更新:day69。

## 0. 每次先跑

```powershell
git pull origin claude/lucid-ritchie-myhksz
python -m pip install -r requirements.txt
python -m pytest tests -q
```
預期:**921 passed, 1 xfailed**(day69 在雲端的結果;那 1 個 xfail 是記錄引擎 bug 的測試，正常)。有其他失敗先停下來回報。`pip install` 這次會裝新的 `fastapi`、`uvicorn`、`httpx`。

## 1. 暫停中:C1 第 4 步(等引擎 bug 決定)

**先不要跑**。day69 發現遊戲引擎的 bug:面對 all-in 的玩家沒有機會跟注或棄牌(`docs/proposals/ENGINE-all-in-round.md`)。所有 checkpoint 都在這個錯誤規則下訓練，修正後要從 0 重訓;在舊規則上訓練到 32k(約 9 小時)沒有意義。

核准修正後，這一節會改成「用新引擎從 0 訓練」的指令。原本的指令保留在 `docs/C1_DESIGN.md` 8.11 作紀錄。

## 2. 可以跑(選擇性)

| 指令 | 時間 / 記憶體 | 目的 |
|---|---|---|
| `python -m product.api.app --checkpoint checkpoints/production_v1.chk.gz --solution v1 --iterations 20000`,然後開 http://127.0.0.1:8000/docs | 載入約 30 秒 / 2 GB | 親手試 D1 的 API(Ctrl+C 結束) |

## 3. 需要你決定 / 審核的(不用跑)

- **[優先] 引擎 bug 修正**:`docs/proposals/ENGINE-all-in-round.md`。核准後我實作修正和測試，並給你重訓的指令。
- **D3**:`docs/HAND_TAXONOMY.md` 第 6 節(v1 方向)。
- **D1**:`docs/API.md` 第 10 節(第一階段已實作)。
