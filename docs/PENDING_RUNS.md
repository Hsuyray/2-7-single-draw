# 待執行清單(筆電)

雲端 session 寫好程式、但需要在筆電上跑的東西，依順序列在這裡。跑完一項就刪掉那一項，並把結果檔 commit 進去。

最後更新:day72。

## 0. 先 commit 16k 的結果(day72)

```powershell
git pull origin claude/lucid-ritchie-myhksz
git add solutions/manifest.json solutions/hu_d5_full_bucket_s20_e70/eval
git commit -m "day72: hu_d5_full_bucket_s20_e70 16k trained and evaluated"
git push origin claude/lucid-ritchie-myhksz
```
16k 的收斂報告寫在 `eval/` 裡(`eval/convergence__016000__s2027.json`),所以上面加 `eval` 就包含它。`day71_*.log` 不要 commit。

## 1. C1:`hu_d5_full_bucket_s20_e70` 訓練到 32k

16k 的結果在 `docs/EXPERIMENT_LOG.md`「C1 new-engine solution, 16k (day72)」。依序跑(一步失敗就停):

```powershell
powercfg /change standby-timeout-ac 0
python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { Write-Host "=== TESTS FAILED ===" } else {
  python -m scripts.solve_library train hu_d5_full_bucket_s20_e70 --until 32000 2>&1 | Tee-Object -FilePath day72_train.log
  if ($LASTEXITCODE -ne 0) { Write-Host "=== TRAIN FAILED ===" } else {
    python -m scripts.inspect_state_convergence solutions/hu_d5_full_bucket_s20_e70/training.state.gz 2>&1 | Tee-Object -FilePath day72_convergence.log
    if ($LASTEXITCODE -ne 0) { Write-Host "=== CONVERGENCE FAILED ===" } else {
      python -m scripts.solve_library evaluate hu_d5_full_bucket_s20_e70 32000 2>&1 | Tee-Object -FilePath day72_eval.log
      python -m scripts.solve_library status hu_d5_full_bucket_s20_e70 2>&1 | Tee-Object -FilePath day72_status.log
      Write-Host "=== ALL DONE ===" 
    }
  }
}
```

- [推測] 16k → 32k 是 16,000 次迭代：訓練約 9.5–15 小時(依筆電狀況，每 500 次 1,060–1,700 秒),評估約 4–6 小時，合計約 14–21 小時。峰值記憶體約 5 GB。
- 中斷了用同一段再貼一次，會從最後存檔續跑。
- 跑完 commit `solutions/manifest.json` 和 `solutions/hu_d5_full_bucket_s20_e70/eval/`,把 `day72_convergence.log`、`day72_status.log` 貼給我。

## 2. 可以跑(選擇性)

| 指令 | 時間 / 記憶體 | 目的 |
|---|---|---|
| `python -m product.api.app --checkpoint checkpoints/production_v1.chk.gz --solution v1 --iterations 20000`,然後開 http://127.0.0.1:8000/docs | 載入約 30 秒 / 2 GB | 親手試 D1 的 API(Ctrl+C 結束) |

## 3. 需要你決定 / 審核的(不用跑)

- **D3**:`docs/HAND_TAXONOMY.md` 第 6 節(v1 方向)。
- **D1**:`docs/API.md` 第 10 節(第一階段已實作)。
