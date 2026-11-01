# C1 設計：可續跑訓練與解庫(solution library)

狀態：**已核准**(day59,第 6 節 a–f 依建議:a = 選項 A,e = 不動)。第 7 節第 1–3 步已實作(紀錄見第 8 節);第 4 步(第一份解的訓練)待你在筆電跑。設計本文依據 `main` @ `6205caa`。

標記：**[確認]** = 已用程式或實測驗證;**[推測]** = 推論。

---

## 0. 範圍說明

- 開場 prompt 用的是 A2 的「盤點 evaluate / inspect script、設計單一評估入口」。這件事 **A2 已經做完**:盤點在 `docs/A2_DESIGN.md` 第 1 節，單一入口是 `scripts/evaluate_checkpoint.py`(day44–56)。C1 不重做，只**呼叫**它。
- 本文件把同樣的做法套到 C1 自己的範圍：先盤點**產生 checkpoint 的訓練 script**,再設計**單一訓練入口**(可續跑訓練 + 解庫)。

---

## 1. 盤點

### 1.1 會訓練的 script

| Script | 擁有者 | 用途 | 遊戲設定 | 存檔 | 狀態 |
|---|---|---|---|---|---|
| `save_training_checkpoint.py` | **C1** | 正式訓練入口 | CLI(stack、max_draw、sizing…);blinds 1/2、ante 1.5 寫死 | 只存平均策略(v3) | 可用;**無法續跑** |
| `profile_memory.py` | A1 | 記憶體量測(RSS CSV、tracemalloc) | 同上，訓練迴圈另寫一份 | 可選 | 可用 |
| `fingerprint_node_store.py` | A1 | 固定 seed 的節點表指紋(等價證明) | 寫死 stack 20、fast | 無 | 可用;C1 的測試會用到它 |
| `run_training.py` | 無(舊) | 舊的診斷用訓練，印 sanity spot | 寫死 stack 100、`max_draw=3`、不加注、**button 交替** | 無 | 舊工具，不是正式路徑 |
| `smoke_train.py` | 無(舊) | 冒煙測試 | 寫死 bucket + `candidate` | 無 | **[確認] 壞掉**:啟動就 `ValueError`(bucket 不支援 candidate) |
| `run_sanity_training.py` | 無(舊) | 固定手牌的 spot 訓練 | 寫死 bucket + candidate | 無 | **[確認] 壞掉**:同一個 `ValueError` |
| `inspect_*`(約 10 支，見 A2 1.1) | A2 / B | 重訓再量 | 各自寫死 | 無 | A2 已用 checkpoint 評估取代 |

### 1.2 重複的部分

1. **訓練迴圈有 2 份**(`save_training_checkpoint`、`profile_memory`),game factory 有 4 種寫法以上(閉包計數器、`TrainingGameFactory`、`FixedTrainingGameFactory`、各 inspect script 自己的)。
2. **`GameConfig(1/2/1.5)` 在約 15 支 script 裡寫死**。目前所有正式 checkpoint 都用這組 blinds,但解庫要多種深度時，設定必須只有一個來源。
3. **`resolve_bet_sizing` 複製多份**(A2 已記錄)。

### 1.3 C1 必須解決的缺口

1. **[確認] 不能續跑。** checkpoint 只存平均策略;regret、strategy sum、RNG 狀態、game 計數器都沒存。RSS guard 觸發或機器重開，訓練就從 0 開始。`full` 40k 估計約 14 小時(A1),一次跑完不實際。
2. **[確認] metadata 沒有 seed / seed_mode。** 無法從 checkpoint 本身重現訓練。
3. **[確認] 沒有「哪份是正式解」的紀錄。** `checkpoints/` 裡 9 份檔案，名稱是唯一線索;`production_v2_maxdraw5_v2.chk.gz` 內容不明就是這個問題。
4. checkpoint 沒有 regret,所以 A2 報告的 current-vs-average 一直是 `available: false`。

---

## 2. 可續跑訓練

### 2.1 原型驗證(day59,容器,只在 scratchpad,沒改 repo)

`bucket`、`max_draw=5`、`fast`、seed 42:
- 連續訓練 60 次 vs 訓練 30 次 → `pickle` 整個 `CFRTrainer` → 讀回 → 再訓練 30 次。
- **[確認] 兩者指紋(`fingerprint_node_store.fingerprint_trainer`)完全相同**:13,209 個節點，sha256 相同。13,209 也和 A1 第 9.2 節 60 次 fast 的節點數一致。
- **[確認] game seed 可以用 `seed + completed_iterations` 推出來。** 每次迭代只呼叫 factory 一次，所以從 0 開始時等於現在的閉包計數器;game 計數器不必另外存。
- **[確認] interning 的共用表在 pickle 後仍然存在**(pickle 的 memo 保留了物件共用)。

所以續跑需要的狀態只有：節點表(含 regret、strategy sum、計數器)、`_random` 的狀態、`completed_iterations`,而這些都在 `CFRTrainer` 物件裡。

### 2.2 格式：兩個選項

| | **A. 另存訓練狀態檔(建議)** | B. checkpoint 升 v4,內含 regret |
|---|---|---|
| 檔案 | `<name>.chk.gz`(v3,不變)+ `<name>.state.gz`(新) | 一個 v4 檔 |
| 凍結介面 | **不動 v3**;查詢、A2 評估、D1 都不受影響 | 升版本;所有讀取端都要處理 v4 |
| 給使用者的檔案大小 | 不變 | 變大 **[推測] 約 2 倍**(多一份 regret dict) |
| 讀取記憶體 | 評估只讀小檔 | 評估也要讀 regret,v2 規模已經要 8 GB |
| 缺點 | 兩個檔案要對得上(用 sha256 綁定) | |

**建議 A。** WORKSTREAMS 的 C1 節寫「會改 schema,需要升版本」,但選項 A 不改 checkpoint schema,只新增一種只給訓練用的檔案，有自己的版本號 `TRAINING_STATE_VERSION = 1`。這是在選項 B 之外的另一種做法，請你決定。

### 2.3 訓練狀態檔的內容(選項 A)

gzip + pickle,用和 checkpoint 一樣的「先寫 `.tmp` 再 replace」:

```
{
  "state_version": 1,
  "trainer": CFRTrainer,          # 節點表、regret、strategy sum、計數器、RNG、completed_iterations
  "run": {
    "seed": 42, "seed_mode": "sequential",
    "cli_config": {...},          # 所有影響結果的參數
    "git_commit": "...", "python": "3.12.9",
    "wall_seconds_total": ..., "peak_rss_gb_max": ...,
    "segments": [ {start_iter, end_iter, wall_seconds, peak_rss_gb, stop_reason}, ... ]
  }
}
```

續跑規則:
- 讀回後比對 `cli_config`;任何影響結果的參數不同就拒絕(例如 stack、sizing、max_draw、abstraction、seed)。只有 `--iterations`(目標總數)、batch、記憶體門檻可以改。
- Python 版本不同時警告但允許:pickle 的 float 是精確的，但 A1 說過指紋只能在同一個版本內比較 **[推測] 續跑後的結果仍然正確，只是不能保證和不中斷的那次逐位相同**。
- 新的狀態檔寫好後，舊的改名成 `.state.gz.prev` 保留一份，寫到一半當機時還有上一份。

### 2.4 停止條件

- RSS guard、可用記憶體不足：存**狀態檔**和策略檔後結束，結束碼不同於正常完成，log 會寫明用 `--resume` 繼續。
- 每 N 個 batch 存一次狀態檔(取代現在的「每 batch 存一次策略檔」)。策略檔只在指定的迭代點和最後存。

### 2.5 記憶體風險(需要實測)

- 存狀態檔要 pickle 整個節點表，比存策略檔(只有平均策略)大。A1 實測:`full` 2k、562k 個節點，存策略檔時進程峰值 1.38 GiB。
- **[推測]** 狀態檔的暫時增量約為策略檔的 2 倍(多了 regret、strategy sum 兩個 dict 和計數器)。`full` 上限 2.03M 個節點時，峰值可能到 5–7 GiB。這是假設，C1 實作後第一個實測項目。
- 若峰值太高，備案是把 regret / strategy sum 改成陣列再存(A1 第 7 節「dict 改陣列」),但那會動到 `cfr_node.py`(A1 擁有),要另外提案。

---

## 3. 解庫

### 3.1 目錄與 manifest

```
solutions/
  manifest.json                         # 進 git
  hu_d5_full_bucket_s20/                # 一份解一個目錄(檔案本身 gitignore)
    strategy_08000.chk.gz               # 指定迭代點的平均策略(v3)
    strategy_16000.chk.gz
    training.state.gz                   # 最新的訓練狀態(可續跑)
    training_log.jsonl                  # 每個 batch 一行：迭代、節點數、時間、RSS
```

`manifest.json` 每份解一筆:
- `id`、`status`(`training` / `evaluated` / `released`)
- 遊戲設定(player_count、stack、blinds、ante、max_draw)、抽象(abstraction、sizing、draw_action_mode、traversal)、seed / seed_mode
- 每個迭代點：策略檔路徑與 sha256、節點數、累計時間、峰值 RSS、A2 報告路徑、gates 結果與 SBR 下界
- `released`:對外使用的是哪個迭代點
- `git_commit`、`code_note`

檔案的實體存放沿用 A0 的建議(GitHub Releases 或 LFS);manifest 用 sha256 綁定。

### 3.2 設定矩陣

- blinds 1/2、BB ante 1.5,所以 1 bb = 2 chips;現在的 stack 20 = **10 bb**。
- **[推測] 深度越大，`full` 下注的加注層數越多，節點上限會成長得很快**。stack 20 的 `full` 上限已經是 2.03M(A1),100 bb 在 16 GB 筆電上很可能跑不動。
- 建議分兩步:
  1. **第一份**:10 bb(stack 20)、`max_draw=5`、`full`、bucket。和 v2 同一個遊戲，可以直接和 v2 的 A2 報告比較，驗證「訓練更久」是否真的降低可剝削度。
  2. 加深度之前，先用 A1 的 `enumerate_public_tree.py`(唯讀使用)量 15 / 20 / 25 / 50 bb 的節點上限，再用 4 KB/節點(穩態)+ 存檔增量估記憶體，然後再定矩陣。

### 3.3 「多少迭代才夠」

- 在 8k、16k、32k、…(每次加倍)存策略檔，每一份都跑 A2 `standard`。
- **停止規則(提案)**:gates PASS;或 SBR 下界連續兩次加倍都沒有下降超過 2 個 SE(到平台期，再訓練也沒用，要回頭找抽象問題)。
- 成本：v2 規模一份 A2 報告約 3.1 小時、8 GB。訓練和評估不能同時在筆電上跑。

---

## 4. 單一訓練入口

```
python -m scripts.solve_library train   <id>        # 依 manifest 開始或續跑
python -m scripts.solve_library status  [<id>]      # 進度、迭代點、gates
python -m scripts.solve_library evaluate <id> <iter> # 呼叫 evaluate_checkpoint,把結果寫回 manifest
python -m scripts.solve_library release <id> <iter>
```

- 訓練迴圈從 `save_training_checkpoint.py` 搬到新檔 `solver/training_run.py`(C1 新增並擁有),兩個 script 共用。
- `save_training_checkpoint.py` 新增 `--state-output` 和 `--resume`;**不加這兩個參數時，輸出和現在完全相同**(第 5 節 T2 證明)。
- `GameConfig` 只從 manifest 或 CLI 產生，不在新程式裡寫死。
- `profile_memory.py`(A1)、`fingerprint_node_store.py`(A1)、`evaluate_checkpoint.py`(A2)不改，只呼叫。
- 壞掉的 `smoke_train.py`、`run_sanity_training.py` 不屬於 C1,只回報(見第 6 節 e)。

---

## 5. 驗證方式

| # | 測試 | 預期 | 推翻條件 |
|---|---|---|---|
| T1 | 連續 N+M 次 vs N 次 → 存狀態 → 讀回 → M 次;bucket / exact、sequential / fixed、續跑兩次 | 指紋完全相同 | 任何不同 = 有沒被保存的狀態(例如全域 `random`、計數器),設計要修正後才能用 |
| T2 | `save_training_checkpoint.py` 不加新參數，改動前後 | 節點指紋與 `strategies()` 完全相同 | 不同 = 搬移迴圈時改到行為 |
| T3 | 用不同 stack / sizing / seed 續跑 | 拒絕，錯誤訊息列出差異 | 能續跑 = 會混出無效的解 |
| T4 | 存狀態檔途中中斷 | 上一份 `.state.gz` / `.prev` 仍可讀 | 讀不到 = 原子寫入有漏洞 |
| T5 | 筆電:`full` 2k 存狀態檔(你跑) | 記錄峰值 RSS 與檔案大小;峰值 < 3 GiB 即可接受 | 峰值 > 2× 存策略檔(1.38 GiB)→ 先處理 2.5 節的備案 |
| T6 | `pytest tests -q` | 全部通過 | |

---

## 6. 需要你決定的事

- **a. 格式**:選項 A(另存狀態檔,v3 不變，建議)或 B(升 v4)。
- **b. 第一份解**:10 bb、`max_draw=5`、`full`、bucket、seed 42,目標先到 32k(分次續跑)。可以嗎?
- **c. 停止規則**:3.3 節的「gates PASS 或連續兩次加倍沒有改善」。
- **d. seed 寫在哪**:建議寫在 manifest 和狀態檔，不改 v3 metadata(改了就要升版本)。
- **e. 壞掉的舊 script**:`smoke_train.py`、`run_sanity_training.py` 啟動就報錯。選項：修成 `draw_action_mode="auto"`、標為 deprecated、或不動。它們沒有擁有者，要你決定由誰處理。
- **f. button 位置**:解庫的解都只有 `button_seat=0`。button 1 的查詢要靠 D1 的座位對調，C1 不處理，只在 manifest 註明。

## 7. 實作順序(核准後)

1. `solver/training_run.py` + `save_training_checkpoint.py --state-output / --resume`;T1–T4、T6。
2. 你在筆電跑 T5(`full` 2k)。
3. `scripts/solve_library.py` + `solutions/manifest.json`。
4. 第一份解：分次訓練到 8k → A2 評估 → 依停止規則繼續。
5. (另外提案給 A2)A2 讀狀態檔，補上 current-vs-average。

## 8. 實作紀錄(day59,第 7 節第 1 步)

### 8.1 檔案

- **新增** `solver/training_run.py`(C1 擁有):`TRAINING_STATE_VERSION = 1`、`TrainingState` / `TrainingRunInfo`、`save_training_state`(`.tmp` → 舊檔改名 `.prev` → 新檔就位)、`load_training_state`、`make_game_factory`(game seed = `seed + trainer.completed_iterations`)、`config_differences`。
- **修改** `scripts/save_training_checkpoint.py`:新增 `--state-output`、`--resume`、`--state-every-batches`(預設 1);`parse_args` / `main` 可傳 `argv`(給測試用);停止時存了狀態檔的話，結束碼 3。
- **新增** `tests/test_training_run.py`(11 個測試)。

### 8.2 和設計的差異

- **訓練迴圈沒有搬到 `solver/training_run.py`**,仍留在 `save_training_checkpoint.py`。這一步只需要狀態檔的讀寫和 game factory,搬迴圈是較大的重構;等第 3 步 `solve_library.py` 真的需要共用時再搬(到時候再做一次 T2)。
- `--iterations` 在續跑時是**目標總數**。從 0 開始時和原本的意思相同;中斷後用同一行指令加 `--resume` 就能接著跑。已達目標時會拒絕。
- 續跑時比對的設定:`player_count`、`stack`、blinds、ante、`max_draw`、`abstraction`、`traversal_mode`、`draw_action_mode`、`bet_sizing`、`seed`、`seed_mode`。batch、記憶體門檻、輸出路徑可以改。Python 版本不同時目前**不警告**(只記在 `run.python_version`)。
- 最後一個 batch 不另存中間狀態檔，只在結束時存一次(避免大規模時存兩次)。
- 每次存檔都把這段的 `{start_iteration, end_iteration, wall_seconds, peak_rss_gb, stop_reason}` 寫進 `run.segments`;續跑會接在前面的 segment 後面。

### 8.3 驗證

| # | 結果 |
|---|---|
| T1 | **通過**。exact / sequential、exact / fixed(full sizing)、bucket / `max_draw=5`:4 次 → 續跑到 7 → 續跑到 10,和直接 10 次的節點指紋與策略檔完全相同;segments 為 (0,4)(4,7)(7,10)。另外:RSS guard 觸發(門檻 0.001 GB)→ 結束碼 3、狀態檔在 2 次 → 續跑到 6,和直接 6 次相同。跨 process 的手動檢查(30 + 30 vs 60,bucket、`max_draw=5`、fast、seed 42,Windows / Python 3.12):13,209 節點，sha256 相同。 |
| T2 | **通過**。不加新參數，改動前後:bucket / `max_draw=5` / fast / 40 次 / batch 15(RSS guard 開)和 exact / `max_draw=1` / full / fixed seed 7 / 30 次 / batch 10(RSS guard 關),策略檔(8,916 / 1,882 個策略)完全相同，metadata 只差 `created_at_utc`,stdout 除了時間與記憶體數字外相同。 |
| T3 | **通過**。改 `--stack`、`--seed`、`--bet-sizing`、`--seed-mode` 續跑都被拒絕，錯誤訊息列出差異。 |
| T4 | **通過**。寫入途中中斷(在 `pickle.dump` 丟例外)→ 原狀態檔不變、沒有殘留 `.tmp`;下一次成功寫入後舊檔在 `.prev`。 |
| T5 | **通過**(day60,筆電，見 8.5)。存狀態檔的峰值不超過存策略檔的峰值;`full` 2k 的整個 process 峰值約 1.5 GB,遠低於 3 GiB。 |
| T6 | **通過**。`python -m pytest tests -q`:874 passed。 |

### 8.4 T5 指令(筆電)

```
python -m scripts.save_training_checkpoint --iterations 2000 --max-draw 5 --abstraction bucket --bet-sizing full --seed 42 --batch-size 500 --max-rss-gb 0 --output experiments/c1/t5_full_2k.chk.gz --state-output experiments/c1/t5_full_2k.state.gz
```

要記的:每個 batch 的 `CFR_nodes`、最後的 `peak_rss_gb`(狀態檔裡 `run.segments[-1]`)、`.state.gz` 和 `.chk.gz` 的檔案大小、總時間。判斷：峰值 < 3 GiB 可接受;> 2 × 1.38 GiB 就先處理 2.5 節的備案。`--max-rss-gb 0` 是為了量到真正的峰值，不讓 guard 提前停。

### 8.5 T5 結果(day60,使用者筆電)

`full` sizing、bucket、`max_draw=5`、seed 42、2,000 次、batch 500,RSS guard 關。

| 項目 | 數值 |
|---|---|
| 節點數(每 500 次) | 213,501 / 356,412 / 471,899 / 562,244(和 A1 的 2k `full` 約 562k 一致) |
| 訓練時間 | batch 1–3 約 620–675 秒,batch 4 為 1,010 秒;總共 3,063 秒 |
| 檔案大小 | `.chk.gz` 5.6 MB、`.state.gz` 16.4 MB(1,500 次的 `.prev` 13.0 MB) |
| 狀態檔裡的 `peak_rss_gb` | 500–1,500 次 1.20 GB,2,000 次 1.42 GB |
| 另外量測(重新載入 2k 狀態後依序存檔) | 載入 7.0 秒、RSS 1.05 GB;存策略檔 18.9 秒，峰值升到 1.535 GB;**再存狀態檔 13.8 秒，峰值不變**(仍 1.535 GB) |

解讀:
- **[確認] 存狀態檔不是記憶體瓶頸。** 峰值來自存策略檔(和 A1 的 1.38 GiB 同一個量級);存狀態檔的暫時增量比較小。2.5 節的「峰值 5–7 GiB」推測被推翻，備案(dict 改陣列)不需要。
- **[確認] 量測缺口：** 狀態檔裡的 `peak_rss_gb` 是在寫狀態檔**之前**讀的，不包含這次存檔本身的峰值。已改成存檔後在 stdout 多印一行 `peak RSS including this save`;檔案格式不變。上表的存檔峰值是另外重新載入後量的，和訓練中的 process 不完全相同(訓練中的 RSS 在存檔前已約 1.4 GB),所以訓練中實際峰值 **[推測]** 約 1.5–1.9 GB。
- **[推測]** 節點上限 2.03M 時，依節點數線性外推：載入後約 3.8 GB,存檔峰值約 5.5 GB。可以在 16 GB 上跑，但不能同時跑 A2 評估(v2 規模約 8 GB)。
- 狀態檔只有策略檔的約 3 倍大，存 / 讀各約 10–20 秒，和一個 batch 的 600 秒以上相比可以忽略，所以預設每個 batch 存一次沒問題。
- batch 4 比前三個慢約 50%,節點成長反而變慢;原因未查(可能是筆電上其他負載)。不影響 T5 的結論。

**結論**:第 7 節第 2 步完成，可以進第 3 步(`scripts/solve_library.py` + `solutions/manifest.json`)。

### 8.6 第 3 步:解庫(day62)

**檔案**
- **新增** `solver/solution_library.py`:manifest 讀寫(`.tmp` → replace)、`new_solution_entry`、`training_argv`、`checkpoint_record`、`evaluation_summary`、`stopping_advice`。
- **新增** `scripts/solve_library.py`:`add` / `train` / `status` / `evaluate` / `release`。
- **新增** `solutions/manifest.json`:第一份解 `hu_d5_full_bucket_s20`(10 bb、`max_draw=5`、`full`、bucket、seed 42,milestone 8k / 16k / 32k,狀態 `planned`)。
- **修改** `solver/training_run.py`:存狀態檔後另寫 `<state>.json`(迭代數、節點數、segments),讀進度不必 unpickle 整個 trainer。
- **修改** `scripts/save_training_checkpoint.py`:`main()` 回傳小的 summary dict(原本回傳 `None`)。
- **修改** `.gitignore`:`solutions/` 下的 checkpoint 和狀態檔不進 git;manifest 和 eval 報告進 git。
- **新增** `tests/test_solve_library.py`(11 個測試)。

**和設計的差異**
- **訓練迴圈仍沒有搬**。`train` 直接呼叫 `save_training_checkpoint.main()`,每個 milestone 一次(`--iterations <milestone> --resume`),所以不需要搬迴圈，也不用再證明一次等價。
- 檔案名稱:`solutions/<id>/strategy_008000.chk.gz`、`training.state.gz`(+ `.prev`、`.json`)、`eval/`。訓練中先寫 `strategy_latest.chk.gz`,到達 milestone 才改名，所以有 milestone 名稱的檔案一定是完整的。訓練時 `--checkpoint-every-batches 0`,中間只存狀態檔。
- 設計裡的 `training_log.jsonl` 沒做:每段的時間和峰值已經在狀態檔的 segments 裡。
- manifest 的 `status`:`planned` → `training` → `trained` → `released`。設計寫的 `evaluated` 改成記在每個 checkpoint 的 `evaluation` 欄位，因為每個 milestone 各自評估。
- `release` 要求有 `standard` preset 的評估;gates 不是 PASS 時要加 `--allow-fail`。released 之後 `train` 會拒絕。
- `train` 預設 `--max-rss-gb 10`(訓練 script 預設 3,`full` 到約 2M 節點時會被擋)。
- 停止規則(3.3)在 `status` / `evaluate` 只給建議，不會自動停：只看 `standard` 評估;最新一份 PASS → 停;最近兩次 milestone 間的 SBR mean gain 下降都不超過 2 × √(SE₁² + SE₂²) → 停(平台期)。
- blinds 只支援 1 / 2 / 1.5(訓練 script 寫死);manifest 存了 blinds,不一樣時 `add` / `train` 會拒絕。要支援其他 blinds 要先改訓練 script。

**驗證**
- `pytest tests -q`:885 passed(新增 11 個)。
- 每個 milestone 的策略檔和「直接訓練到同樣次數」完全相同(3 / 6 次，分兩次 `train`);記憶體停止(結束碼 3)後同一行指令續跑，結果仍相同;「訓練完但還沒記錄」的情況會直接補記錄，不重訓。
- 用真的 v2 standard 報告測 `evaluation_summary`:verdict FAIL、Q6 下界 1.53(和 A2_DESIGN 13 節相同)。
- T2 再做一次：不加新參數時兩組設定的策略檔仍和改動前完全相同。
- CLI 實跑(scratchpad,bucket、`max_draw=1`、20 / 40 次 + `evaluate --preset quick`):檔案和 manifest 如上。

### 8.7 第 4 步指令(筆電)

```
python -m scripts.solve_library train hu_d5_full_bucket_s20 --until 8000
python -m scripts.solve_library status
python -m scripts.solve_library evaluate hu_d5_full_bucket_s20 8000
```

- **[推測]** 時間:T5 的 2k 花了約 51 分鐘，每次迭代會隨節點變多而變慢，所以 8k 約 4–6 小時;評估約 3 小時、8 GB(v2 規模),不能和訓練同時跑。
- 中斷(關機、記憶體不足)後再跑同一行 `train` 就會續跑。
- 8k 的評估可以直接和 v2(同一個遊戲、也是 8k)比較：兩者應該是同一個量級;差很多就表示訓練流程有問題，要先查。
- 評估完把 `solutions/manifest.json` 和 `solutions/hu_d5_full_bucket_s20/eval/` commit 進去。
