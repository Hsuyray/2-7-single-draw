# 待執行清單(筆電)

雲端 session 寫好程式、但需要在筆電上跑的東西，依順序列在這裡。跑完一項就刪掉那一項，並把結果檔 commit 進去。

最後更新:day73。

## 0. 先 commit 32k 的結果(day73)

```powershell
git add solutions/manifest.json solutions/hu_d5_full_bucket_s20_e70/eval
git commit -m "day73: hu_d5_full_bucket_s20_e70 32k trained and evaluated"
git pull origin claude/lucid-ritchie-myhksz
git push origin claude/lucid-ritchie-myhksz
```
`day72_*.log` 不要 commit。

## 1. C1:`hu_d5_full_bucket_s20_e70` 訓練到 64k(建議;要不要跑由你決定)

32k 的結果在 `docs/EXPERIMENT_LOG.md`「C1 new-engine solution, 32k (day73)」。`status` 說「stop: plateaued」是誤判(`docs/C1_DESIGN.md` 8.12):SBR 每次都在下降。第一行把 64000 加進這個解的 milestones。

```powershell
powercfg /change standby-timeout-ac 0
python -c "import json;p='solutions/manifest.json';m=json.load(open(p,encoding='utf-8'));e=m['solutions']['hu_d5_full_bucket_s20_e70'];e['milestones']=sorted(set(e['milestones']+[64000]));open(p,'w',encoding='utf-8').write(json.dumps(m,indent=2,sort_keys=True)+'\n')"
python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { Write-Host "=== TESTS FAILED ===" } else {
  python -m scripts.solve_library train hu_d5_full_bucket_s20_e70 --until 64000 2>&1 | Tee-Object -FilePath day73_train.log
  if ($LASTEXITCODE -ne 0) { Write-Host "=== TRAIN FAILED ===" } else {
    python -m scripts.inspect_state_convergence solutions/hu_d5_full_bucket_s20_e70/training.state.gz 2>&1 | Tee-Object -FilePath day73_convergence.log
    if ($LASTEXITCODE -ne 0) { Write-Host "=== CONVERGENCE FAILED ===" } else {
      python -m scripts.solve_library evaluate hu_d5_full_bucket_s20_e70 64000 2>&1 | Tee-Object -FilePath day73_eval.log
      python -m scripts.solve_library status hu_d5_full_bucket_s20_e70 2>&1 | Tee-Object -FilePath day73_status.log
      Write-Host "=== ALL DONE ==="
    }
  }
}
```

- [推測] 32k → 64k 是 32,000 次迭代 = 64 批 × 約 1,050 秒 ≈ **18.5 小時**,加評估約 3.5–4 小時，合計約 **22–23 小時**。
- 記憶體：訓練中約 3.5 GB,最後存檔時峰值約 6.5 GB。32k 時剩餘記憶體只有約 2.8 GB(最低限制 2 GB),**跑的時候請關掉其他大程式**(瀏覽器等)。萬一因記憶體停下，狀態會留在最後一批，關掉程式後再貼一次同一段就會續跑。
- 跑完 commit `solutions/manifest.json` 和 `solutions/hu_d5_full_bucket_s20_e70/eval/`,把 `day73_convergence.log`、`day73_status.log` 貼給我。

## 2. 可以跑(選擇性)

| 指令 | 時間 / 記憶體 | 目的 |
|---|---|---|
| `python -m product.api.app --checkpoint checkpoints/production_v1.chk.gz --solution v1 --iterations 20000`,然後開 http://127.0.0.1:8000/docs | 載入約 30 秒 / 2 GB | 親手試 D1 的 API(Ctrl+C 結束) |

## 3. 需要你決定 / 審核的(不用跑)

- **D3**:`docs/HAND_TAXONOMY.md` 第 6 節(v1 方向)。
- **D1**:`docs/API.md` 第 10 節(第一階段已實作)。
