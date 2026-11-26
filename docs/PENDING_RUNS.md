# 待執行清單(筆電)

雲端 session 寫好程式、但需要在筆電上跑的東西，依順序列在這裡。跑完一項就刪掉那一項，並把結果檔 commit 進去。

最後更新:day76。

## 1. 推上 e70s 8k 的結果，並跑對打(約 5 分鐘)

訓練和評估已完成(day76),結果已寫進 `docs/EXPERIMENT_LOG.md`。筆電上 manifest 和評估報告還沒推上來，另外補一個只跑對打的短評估(e70s 對 e70,正值 = simple 贏):

```powershell
git pull origin claude/lucid-ritchie-myhksz
python -m scripts.evaluate_checkpoint solutions/hu_d5_full_bucket_s20_e70s/strategy_008000.chk.gz --previous solutions/hu_d5_full_bucket_s20_e70/strategy_008000.chk.gz --sections previous --out-dir experiments/eval/e70s_vs_e70
git add solutions/manifest.json solutions/hu_d5_full_bucket_s20_e70s/eval experiments/eval/e70s_vs_e70
git commit -m "day76: C1 e70s 8k trained and evaluated; head-to-head vs e70"
git push origin claude/lucid-ritchie-myhksz
```

`--sections previous` 只跑對打，不跑 SBR,所以不是 benchmark 報告，也不會記進 manifest。

## 2. 可以跑(選擇性)

| 指令 | 時間 / 記憶體 | 目的 |
|---|---|---|
| `python -m product.api.app --checkpoint checkpoints/production_v1.chk.gz --solution v1 --iterations 20000`,然後開 http://127.0.0.1:8000/docs | 載入約 30 秒 / 2 GB | 親手試 D1 的 API(Ctrl+C 結束) |

## 3. 需要你決定 / 審核的(不用跑)

- **D3**:`docs/HAND_TAXONOMY.md` 第 6 節(v1 方向)。
- **D1**:`docs/API.md` 第 10 節(第一階段已實作)。
