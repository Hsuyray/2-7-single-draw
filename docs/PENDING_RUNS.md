# 待執行清單(筆電)

雲端 session 寫好程式、但需要在筆電上跑的東西，依順序列在這裡。跑完一項就刪掉那一項，並把結果檔 commit 進去。

最後更新:day71。

## 0. 先 commit 8k 的結果(day71)

```powershell
git pull origin claude/lucid-ritchie-myhksz
git add solutions/manifest.json solutions/hu_d5_full_bucket_s20_e70/eval solutions/hu_d5_full_bucket_s20_e70/convergence__008000__s2027.json
git commit -m "day71: hu_d5_full_bucket_s20_e70 8k trained and evaluated"
git push origin claude/lucid-ritchie-myhksz
```
`day70_*.log` 不要 commit(可以刪)。

## 1. C1:`hu_d5_full_bucket_s20_e70` 訓練到 16k

8k 的結果在 `docs/EXPERIMENT_LOG.md`「C1 new-engine solution, 8k (day71)」。依序跑(一步失敗就停):

```powershell
powercfg /change standby-timeout-ac 0
python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { Write-Host "=== TESTS FAILED ===" } else {
  python -m scripts.solve_library train hu_d5_full_bucket_s20_e70 --until 16000 2>&1 | Tee-Object -FilePath day71_train.log
  if ($LASTEXITCODE -ne 0) { Write-Host "=== TRAIN FAILED ===" } else {
    python -m scripts.inspect_state_convergence solutions/hu_d5_full_bucket_s20_e70/training.state.gz 2>&1 | Tee-Object -FilePath day71_convergence.log
    if ($LASTEXITCODE -ne 0) { Write-Host "=== CONVERGENCE FAILED ===" } else {
      python -m scripts.solve_library evaluate hu_d5_full_bucket_s20_e70 16000 2>&1 | Tee-Object -FilePath day71_eval.log
      python -m scripts.solve_library status hu_d5_full_bucket_s20_e70 2>&1 | Tee-Object -FilePath day71_status.log
      Write-Host "=== ALL DONE ==="
    }
  }
}
```

- [推測] 訓練 8k → 16k 約 4.5–5 小時、峰值約 4 GB;評估約 4 小時。合計約 9 小時。
- 評估時第一行出現紅字 `NativeCommandError` 是 PowerShell 把 stderr 的「Loading ...」當成錯誤顯示，不影響結果(day71 那次也有)。
- 跑完 commit `solutions/manifest.json`、`solutions/hu_d5_full_bucket_s20_e70/eval/` 和新的 `convergence__016000__s2027.json`,把 `day71_convergence.log`、`day71_status.log` 貼給我。

## 2. 可以跑(選擇性)

| 指令 | 時間 / 記憶體 | 目的 |
|---|---|---|
| `python -m product.api.app --checkpoint checkpoints/production_v1.chk.gz --solution v1 --iterations 20000`,然後開 http://127.0.0.1:8000/docs | 載入約 30 秒 / 2 GB | 親手試 D1 的 API(Ctrl+C 結束) |

## 3. 需要你決定 / 審核的(不用跑)

- **D3**:`docs/HAND_TAXONOMY.md` 第 6 節(v1 方向)。
- **D1**:`docs/API.md` 第 10 節(第一階段已實作)。
