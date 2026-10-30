# A2 設計：單一評估入口 `scripts/evaluate_checkpoint.py`

狀態：**已實作**(day44–46)。第 6 節三個待決事項都依建議採用(使用者核准)。實作與設計的差異、量測結果和門檻草案見第 9、10 節。設計本文依據 `main` @ `27b62a7`。

標記：**[確認]** = 已用程式或實測驗證;**[推測]** = 推論。

---

## 1. 現有 script 盤點

### 1.1 和「策略品質評估」直接相關的 script

| Script | 輸入 | 量什麼 | 備註 |
|---|---|---|---|
| `evaluate_strategy_profile.py` | **現場重訓** | 自我對打的 seat 0/1 utility、zero-sum 誤差、整體覆蓋率 | 用 `StrategyProfileEvaluator`(抽樣動作) |
| `inspect_strategy_coverage.py` | 現場重訓 | 各 phase 覆蓋率、缺失 public node / hand key / info set 前 N 名 | 複製了 evaluator 的對局迴圈並呼叫其私有方法 `_uniform_strategy` 等 |
| `inspect_coverage_growth.py` | 現場重訓到多個迭代點 | 覆蓋率隨迭代的變化 | 同上的覆蓋率邏輯再複製一次 |
| `inspect_checkpoint_coverage.py` | **checkpoint** | 各 phase 覆蓋率 | **唯一**讀 checkpoint 的覆蓋率工具;有兩個量測 bug,見 1.3 |
| `inspect_current_vs_average.py` | 現場重訓 | 每節點 current(regret matching)vs average 的 L1,列出前 N 名 | 需要 regret,checkpoint 沒有 |
| `inspect_strategy_convergence.py` | 現場重訓到多個迭代點 | 相鄰迭代點之間 average strategy 的 L1(未加權 / strategy-sum 加權) | 需要 strategy sum 當權重 |
| `inspect_anchored_convergence.py` | 現場重訓到多個迭代點 | 每個迭代點相對**最後一點**的 L1,分 phase | 和上一支幾乎同一套 snapshot / L1 程式碼 |
| `inspect_sampled_best_response.py` | 現場重訓 | SBR proxy:兩個 seat 的 held-out gain | 每個 seat 只跑一次，沒有重複，沒有變異數 |
| `inspect_training_phases.py` | 現場重訓 | 各 phase 節點數、visit、近均勻策略比例、動作分佈 | |
| `inspect_uniform_nodes.py` | 現場重訓 | 近均勻節點清單(含 regret、strategy sum) | |
| `inspect_strategy_checkpoint.py` | checkpoint | metadata、strategy 數、public node 數 | 只讀 metadata 摘要 |
| `query_strategy_checkpoint.py` | checkpoint | 單一節點查詢 | 產品查詢，不是評估 |

和評估無關、A2 不碰的:`inspect_*bucket*`、`inspect_full_postdraw_universe`、`inspect_category_strength_buckets`(抽象設計，B 系列)、`inspect_memory_model`、`inspect_node_composition`、`inspect_state_space_growth`、`profile_memory`、`fingerprint_node_store`、`enumerate_public_tree`(A1)、`run_*`、`smoke_train`、`trace_runaway`、`precompute_starting_ranges`、`export_postdraw_bucket_mapping`。

### 1.2 重複的部分

1. **幾乎全部都「重訓再量」**。12 支裡只有 2 支讀 checkpoint。後果：
   - 評估的不是 `checkpoints/` 裡那份要給使用者的策略，而是「同參數重訓出來的另一份」。
   - 每次評估都要付訓練成本(v2 8k 次約 1.3 小時 **[推測，依 0.59 s/iter]**)。
   - 無法回答「v1 和 v2 哪個好」,因為兩份 checkpoint 本身沒被量過。
2. **樣板程式碼複製約 12 份**:`resolve_bet_sizing`、`make_sequential_factory` / `make_game_factory`、`phase_name` / `phase_label`、`strategy_weight`、`strategy_l1`、`is_near_uniform`、`mapping_values`。遊戲設定(blinds 1/2、ante 1.5)在每支 script 裡硬寫。
3. **覆蓋率算了 4 次**(`evaluate_strategy_profile`、`inspect_strategy_coverage`、`inspect_coverage_growth`、`inspect_checkpoint_coverage`),而且**動作選法不一致**:前三支依策略抽樣，第四支取 argmax。
4. **收斂 L1 算了 3 次**(`inspect_strategy_convergence`、`inspect_anchored_convergence`、`inspect_current_vs_average`),各自有一份 snapshot / L1。
5. **沒有任何一支報告變異數或標準誤**。SBR 只跑一個 seed。

### 1.3 現有工具的量測 bug

**[確認] `inspect_checkpoint_coverage.py` 低估覆蓋率約一半。**

- 證據:`production_v1.chk.gz`,1,000 deals:
  - `inspect_checkpoint_coverage.py`:**51.15%**(predraw 48.9% / draw 53.3% / postdraw 54.4%)
  - 同一 checkpoint 用 `StrategyProfileEvaluator`,button 固定 0:**97.00%**
  - 同上,button 交替 0/1:**52.34%**
- 原因 1(主因,**[確認]**):它用 `button_seat = deal_index % 2`,但所有訓練 factory(含 `save_training_checkpoint.py:349`)都固定 `button_seat=0`,而 `PublicNodeKey` 含絕對 `button_seat`。所以奇數 deal 從第一個決策就全部 miss。
- 原因 2(**[確認]** 程式碼，影響量未單獨測):它直接呼叫 `legal_actions()` + `apply_solver_action()`,沒走 trainer 的 `bucket_solver_actions_for_game` / `executable_bucket_action_for_game`。bucket 模式下 draw 動作和 strategy 的 key 型別不同,`strategy.get(action, 0.0)` 全是 0,argmax 退化成「第一個動作」。
- 原因 3:取 argmax 而非抽樣，所以量到的是「確定性策略走到的狀態」,不是策略實際的 reach 分佈。
- 遊戲設定缺欄位時 fallback 到硬寫的 20/1/2/1.5,v1/v2 schema 的舊檔會悄悄用錯設定。

**[確認] 附帶的產品問題(不屬 A2,轉給 D1 / 凍結介面流程):** 訓練只見過 `button_seat=0`,而 key 用絕對位置。`query_strategy_checkpoint.py --button-seat 1` 這類查詢會全部查不到。2-7 單挑在 seat 重新編號下是對稱的，所以這是「key 沒做 player-relative 正規化」(CLAUDE.md 碎片化 watch-list 的 *absolute vs player-relative positions*),不是缺訓練。修法會動 key 或查詢層，要另開提案。

---

## 2. 設計原則

1. **評估對象 = checkpoint 檔本身**,不重訓。輸入只有 checkpoint 路徑 + 評估參數。
2. **遊戲規則和動作空間完全從 checkpoint metadata 重建**,且走和訓練同一條動作路徑(`CFRTrainer._legal_actions` / `_apply_node_action`,即 `StrategyProfileEvaluator` 現在的做法)。
3. **評估的 deal 分佈 = 訓練的 deal 分佈**(button 0、metadata 的籌碼 / blinds),但用不重疊的 deck seed 範圍。button 1 另外列為診斷，不混進主覆蓋率。
4. **每個 Monte Carlo 數字都附 n 和標準誤**。
5. **可重現**:所有 seed 明確寫在報告裡;每個區段用獨立 RNG,關掉某區段不會改變其他區段的數字;報告去掉計時欄位後應逐 byte 相同。
6. 舊 script **全部保留**(CLAUDE.md:保留診斷 script),不做無關重構。只修 A2 擁有的 `inspect_checkpoint_coverage.py` 的 bug(另一個 commit,可選)。

---

## 3. 介面

```
python -m scripts.evaluate_checkpoint CHECKPOINT
    [--previous PREV_CHECKPOINT]      # head-to-head 對手
    [--preset quick|standard]         # 預設 standard
    [--seed 2027]                     # 所有區段的 seed 由此衍生
    [--deals N] [--sbr-repeats K] [--sbr-response-deals N] [--sbr-validation-deals N] [--sbr-sweeps N]
    [--sections coverage,static,sbr,baseline,h2h]
    [--out-dir experiments/eval]
```

輸出兩個檔(`--out-dir` 底下):
- `<stem>__<sha256 前 8 碼>__<preset>__s<seed>.json`:機器可讀，`sort_keys`,計時放在獨立的 `timing` 欄位。
- 同名 `.txt`:人看的摘要(和 stdout 相同)。

另提供 `python -m scripts.evaluate_checkpoint --compare A.json B.json`:比較兩份報告(忽略 `timing`),列出差異。用來做「跑兩次一致」和版本間比較。

---

## 4. 報告內容(各區段)

### 4.0 識別與設定
- checkpoint 路徑、sha256、檔案大小、`format_version`
- metadata 全部欄位(含 `completed_iterations`;已確認 `production_v2_maxdraw5.chk.gz` 是 8k,見 6.2)
- 重建出的 `GameConfig`、`BetSizingPolicy`、`draw_action_mode`。metadata 缺必要欄位(v1/v2 schema 舊檔)時**直接報錯**,要求用 `--assume-config` 明確指定，不悄悄 fallback。
- 評估參數、全部 seed、python 版本、git commit
- 載入時間、峰值 RSS

### 4.1 靜態統計(不需要模擬)
- 各 phase 的 info set 數、public node 數
- 各 phase 近均勻策略比例(tolerance 1e-6,沿用 `inspect_training_phases` 的定義)、確定性策略(max ≥ 0.999)比例
- 完整性檢查:每個策略總和 = 1(容差 1e-9)、無 NaN / inf / 負值

### 4.2 覆蓋率與缺失狀態(自我對打模擬,`StrategyProfileEvaluator` 的抽樣規則)
- 整體 / 各 phase 覆蓋率 = matched decisions / total decisions,附二項分佈標準誤
- **「第一次缺失」**:每局第一個 miss 發生在哪個 phase。第一次缺失之後，雙方都用 uniform fallback,後面的 miss 多半是連鎖反應，不代表新的洞。這個數字比原始 miss 數更能指出要補哪裡。
- 缺失狀態依「模擬中出現次數」(= 在此 profile 下 reach 的抽樣估計)排序，前 N 名，分兩層:
  - public node(phase、歷史長度、action history、pot、current bet)
  - (phase, hand key)
- **動作空間一致性檢查**:每個 matched decision,比較 strategy 的動作集合和重建出的 legal action 集合。不一致的次數必須是 0;不是 0 就代表 metadata 重建錯，或訓練 / 評估的 legal action 不同(CFR checklist 項目)。
- button 1 診斷：另跑 `--deals / 10` 局 button 1 的覆蓋率，單獨列出，標註見 1.3。
- 同一批模擬順便輸出：seat 0/1 utility ± SE、zero-sum 誤差(每局都檢查，最大值)。

### 4.3 收斂指標(取代 current-vs-average,見 6.1 待決事項)
- 有 `--previous` 且兩者遊戲設定相同時：在共同 info set 上算 average strategy 的 L1,**用 4.2 的 reach 抽樣次數加權**(checkpoint 沒有 strategy sum,不能用訓練權重)。分 phase 報告加權平均、中位數、p90,以及只存在其中一份的 info set 數。
- 這是「兩份解差多少」,不是 exploitability;解讀時要和 SBR 一起看。

### 4.4 SBR proxy
- 呼叫現有 `SampledBestResponse`,**演算法不改**(跨 sweep 累積已試過並還原，不重試)。
- 每個 seat 跑 K 次(`--sbr-repeats`,standard 預設 K=5),每次用不同的 response seed、相同的 validation deal 集合。
- 報告：每次的 held-out gain、K 次的平均 / 標準差 / 最小 / 最大，以及每次的 response deals、validation deals、sweeps、對手策略覆蓋率。
- 再報告 validation 本身的標準誤(baseline value 的 per-deal SE),讓讀者分得出「gain 比噪音大多少」。
- 需要的非演算法改動:`SampledBestResponseResult` 加 per-deal 平方和(才能算 SE)。這是 A2 允許的「非演算法改動」範圍，不改任何 deal 的抽樣或決策。

### 4.5 固定對手 baseline
同一批 deal、**seat 對調各打一次**(duplicate 形式，降低牌運變異),報告 profile 對每個對手的平均 utility/局 ± SE:
- `uniform`:每個 legal solver action 等機率
- `call_station`:能 check 就 check,否則 call;draw 時 pat(換 0 張)
- 是否加入「依 `DrawHandBucket` 的簡單換牌規則」這類較強的手寫對手，留給 B2 提案;A2 先只放上面兩個，介面設計成可以再加。

### 4.6 和前一版 checkpoint 的 head-to-head
- 條件：兩份 checkpoint 的 `GameConfig`、`max_draw`、`draw_action_mode`、下注尺寸、`abstraction` **全部相同**。不同就**拒絕**並列出哪些欄位不同。
  - 原因：雙方必須在同一套規則和同一個動作空間裡下棋。例如 v1(`max_draw=1`)在 `max_draw=5` 的遊戲裡沒有換 2–5 張的策略，硬比的結果是在量 fallback,不是策略品質。
  - 所以 **v1 vs v2 不能做 head-to-head**;v2 vs v2 可以。
- 同一批 deal、seat 對調各打一次，報告 A 對 B 的 utility/局 ± SE,以及雙方的覆蓋率(任一方 miss 太多時 head-to-head 意義有限，報告要標註)。

### 4.7 摘要與門檻
報告最後一段列出：覆蓋率、第一次缺失率、SBR 平均 gain ± sd、對 uniform / call_station 的勝率、H2H。**門檻先不寫死**:v1 和 v2 的基準報告出來後，我再依數字提出門檻給你核准(WORKSTREAMS 第 5 節)。

---

## 5. 程式結構(預計動到的檔案)

全部在 A2 擁有的範圍內。

| 檔案 | 動作 | 內容 |
|---|---|---|
| `solver/checkpoint_evaluation.py` | **new file** | metadata → `GameConfig` / `BetSizingPolicy` 重建;deal factory;靜態統計;覆蓋率模擬(含 first-miss、缺失排序、動作一致性);reach 加權 L1;報告 dataclass → dict |
| `solver/strategy_profile_evaluator.py` | **overwrite existing file**(小改) | (a) `_play_one_game` 加可選的 per-decision observer callback,讓覆蓋率統計不用再複製迴圈;(b) 累計 per-deal utility 平方和以算 SE;(c) 新增 `HeadToHeadEvaluator`(兩個 StrategyIndex 各控一個 seat)和固定對手策略。(a)(b) 不改任何 RNG 呼叫順序 |
| `solver/best_response.py` | **overwrite existing file**(非演算法) | `SampledBestResponseResult` 加 validation per-deal 平方和 |
| `scripts/evaluate_checkpoint.py` | **new file** | CLI、preset、寫 JSON / txt、`--compare` |
| `tests/test_checkpoint_evaluation.py` | **new file** | 見第 7 節 |
| `scripts/inspect_checkpoint_coverage.py` | **overwrite existing file**(可選，獨立 commit) | 修 1.3 的 bug,或改成印一行「請用 evaluate_checkpoint」後呼叫新模組 |

不動：訓練程式、`InformationState` / `PublicNodeKey`、checkpoint schema、其他 inspect script。

---

## 6. 待你決定的事項

> **決定(day44)**:三項都依建議。6.1 採 (A);6.2 先量再定(結果見 9.3);6.3 修(day45 commit)。

### 6.1 current-vs-average 要怎麼處理
checkpoint 只存 average strategy,沒有 regret,所以**從 checkpoint 算不出 current-vs-average**。選項:
- **(A,建議)** 報告裡這一段標為「unavailable: checkpoint has no regrets」,改用 4.3 的版本間 L1 + 4.4 的 SBR 當收斂指標。等 C1 的「可續跑訓練 / schema 加 regret」提案落地後再補。
- (B) 加 `--retrain` 模式：依 metadata 重訓一份再量。問題:metadata **沒有存訓練 seed**,也沒存 `seed_mode`,所以重訓出來的不保證是同一份解;而且 v2 要重訓一個多小時。不建議。
- (C) 提一個 schema 變更，把 seed 和 regret 存進 checkpoint。這是凍結介面，要 version bump、要重訓，屬於 C1 範圍。

### 6.2 SBR 的 standard preset 成本
SBR 在 v2(約 100 萬 info set **[待測]**)上的速度還沒量過。實作第一步會先在 v1 上量 SBR 每 1,000 deals 的時間，再定 standard preset 的 K 和 deal 數。目標：standard 在你的筆電上單一 checkpoint < 30 分鐘;quick < 3 分鐘(給 CI / 開發用)。

參考 **[確認]**(本 container,Python 3.13):
- `production_v1` 載入 + 自我對打 1,000 deals 約 14 秒。
- `production_v2_maxdraw5.chk.gz`:metadata 為 v3 schema、**8,000 次**、`max_draw=5`、`full` 下注比例、128 postdraw bucket、1,068,645 個策略。**光載入就 260 秒**。
- `production_v2_maxdraw5_v2.chk.gz`(59 MB):5 分鐘內沒載完，程序被 kill(exit 137,未查是 timeout 還是記憶體)。它的迭代數還不知道。

因此載入成本本身就是 v2 評估的主要成本之一;評估入口只載入一次，所有區段共用。載入為什麼這麼慢屬於 `strategy_checkpoint.py`(不是 A2 擁有),另外記錄。

### 6.3 是否順手修 `inspect_checkpoint_coverage.py`
建議修(button 固定 0 + 走 trainer 的動作路徑 + 抽樣),因為它現在給出的 51% 會誤導任何讀到它的人。也可以只在 EXPERIMENT_LOG 記錄它不可信、不改 code。

---

## 7. 驗證方式

每一項都寫「預期結果」和「什麼結果代表設計錯了」。

1. **重現性**:同一個小 checkpoint(測試裡用 seed 42 訓練 20 次產生)跑兩次，`--compare` 回報 0 個差異。*推翻*:任何非 `timing` 欄位不同。
2. **區段獨立**:`--sections coverage` 和 `--sections coverage,sbr` 的 coverage 區段完全相同。*推翻*:數字不同(代表 RNG 串流沒分開)。
3. **和現有工具對帳**:對同一個 StrategyIndex,新模組的覆蓋率 = `StrategyProfileEvaluator.evaluate` 的覆蓋率(同 seed、同 deals,完全相等)。*推翻*:不相等。
4. **observer callback 不改行為**:加 callback 前後，`evaluate_strategy_profile.py` 固定 seed 的輸出逐字相同(behavior-preserving 證明)。
5. **動作空間一致性**:`production_v1` 上 mismatch = 0。*推翻*:非 0,代表 metadata 重建有錯，要先修再談其他數字。
6. **H2H sanity**:checkpoint 對自己 H2H,utility 在 0 ± 2 SE 內;對 `uniform` 為正。*推翻*:自己對自己顯著不為 0(代表 seat 對調或 deal 配對有錯)。
7. **H2H 拒絕**:v1 對 v2 回報設定不相容並列出 `max_draw` 等欄位，不產生數字。
8. **完成條件**(WORKSTREAMS A2):v1、v2 各一份 standard 報告存在 `experiments/eval/`,各跑兩次 `--compare` 為 0 差異。

---

## 8. 實作順序(核准後)

1. `solver/checkpoint_evaluation.py` 的 metadata 重建 + 覆蓋率區段 + 測試 1、3、5。在 v1 上出第一份報告。
2. evaluator 的 observer / SE 改動 + 測試 4。
3. SBR 區段，先量成本(6.2),定 preset。
4. baseline + H2H + 測試 6、7。
5. v1 / v2 基準報告、EXPERIMENT_LOG、WORKSTREAMS 狀態表，提出門檻草案。

---

## 9. 實作紀錄(day44–46)

### 9.1 檔案
- **new** `solver/checkpoint_evaluation.py`、`scripts/evaluate_checkpoint.py`、`tests/test_checkpoint_evaluation.py`(13 個測試)。
- **overwrite** `solver/strategy_profile_evaluator.py`:可選 observer、per-deal 平方和、`HeadToHeadEvaluator`、`UniformPolicy` / `CallStationPolicy` / `StrategyIndexPolicy`。
- **overwrite** `solver/best_response.py`:`SampledBestResponseResult` 加 validation 平方和與 SE property,演算法和 RNG 呼叫順序不變。
- **overwrite** `scripts/inspect_checkpoint_coverage.py`(day45,獨立 commit):CLI 與輸出格式不變。

### 9.2 和設計的差異
- 新增「**played 時近均勻比例**」(每 phase):靜態統計發現 70–93% 的已存策略是均勻的，只看靜態數字無法知道這些狀態是否真的會走到，所以在自我對打中量「命中的決策裡有多少是均勻策略」。這是目前最有資訊量的指標之一。
- `--sections` 名稱:`static, coverage, button1, sbr, baselines, previous`(`previous` = 距離 + H2H)。
- 讀 checkpoint 內部 `StrategyIndex._strategies`(唯讀)做靜態統計，避免 `strategies()` 的深拷貝讓 v2 記憶體加倍。
- `--compare` 忽略 `timing` 和 `environment`(python 版本、git commit)。

### 9.3 驗證結果(對應第 7 節)
1. 重現性:測試用不同 `PYTHONHASHSEED` 在兩個 process 跑，`--compare` 0 差異;v1、v2 standard 各跑兩次也 0 差異。
2. 區段獨立：測試通過(coverage 前後夾一次 SBR,結果相同)。
3. 對帳：新模組覆蓋率 = `StrategyProfileEvaluator.evaluate`(同 seed,完全相等)。
4. observer 不改行為:`evaluate_strategy_profile`(200 iters、max_draw 5、fast)和 `inspect_sampled_best_response` 固定 seed 輸出改動前後逐字相同。
5. 動作空間一致性:v1、v2 mismatch 都是 0。
6. H2H:同一份對自己在 4 SE 內;兩個相同的確定性 policy 對調座位結果剛好為 0(驗證 seat 對調)。
7. 拒絕：單元測試驗證 `max_draw` 不同會列出。v1 對 v2 的實跑沒做：兩份同時載入需約 10 GB,和 v2 評估同時跑會超過本 container 記憶體。
8. 完成條件:v1、v2 standard 報告在 `experiments/eval/`。

成本(本 container):v1 standard 14 分鐘、峰值 2.0 GB;v2 standard 49 分鐘(SBR 占 42 分鐘)、**峰值 8.2 GB**(來自載入,`strategy_checkpoint.py`,不屬 A2)。超過原本 30 分鐘的目標;為了讓所有 checkpoint 用同一把尺，先不為 v2 縮小 preset。

---

## 10. 門檻(day48 核准;Q4 day49 修正)

實作在 `solver/benchmark_gates.py`(`GATES_VERSION = 1`),每份新報告都有 `gates` 區段;舊報告用 `python -m scripts.evaluate_checkpoint --gates REPORT.json` 重算。只有 `standard` preset 且沒有覆寫參數的報告算正式 benchmark。

**硬性(正確性，任何一項不過，其他數字都不可信):**
- invalid strategies = 0、action-space mismatches = 0、max zero-sum error ≤ 1e-9
- 同一 checkpoint 兩次報告 `--compare` 0 差異

**品質(提案):**

| # | 指標 | 門檻 | v1 | v2 |
|---|---|---|---|---|
| Q1 | 覆蓋率(button 0) | 整體 ≥ 97%,每 phase ≥ 95% | 不過(draw 94.79%) | 不過 |
| Q2 | 有任何缺失的 deal 比例 | ≤ 10% | 過(9.27%) | 不過(22.41%) |
| Q3 | played 時近均勻比例 | 每 phase ≤ 10% | 不過(draw 23%) | 不過(draw 46%) |
| Q4 | 對 uniform、call_station | **不輸**:utility ≥ -2 SE(原草案「> 3 SE」已撤回，見下) | 過 | 過 |
| Q5 | 對前一版同設定 checkpoint 的 H2H | ≥ -2 SE(不退步) | n/a | n/a |

**SBR 暫不設門檻**:在 standard 的預算下,SBR 找不到比 profile 更好的 response(v2 平均 -0.30,v1 seat 0 五次都是負的)。這把尺目前量不出可剝削度，用它設門檻沒有意義。下一步先做單變數實驗(v1,response deals 100 / 300 / 1,000),看 gain 是否轉正、變異是否收斂，再決定。

**Q4 為什麼改成「不輸」**:這是兩人零和遊戲。用對調座位的 duplicate 格式時，遊戲值是 0,而均衡策略對**任何**對手的期望都 ≥ 0。對手偏離均衡，只會讓均衡策略賺得多或打平，不會讓它被剝削;均衡的缺點是**不會主動最大化**剝削弱對手。所以:
- 顯著輸給固定對手 = 證明這份策略可被剝削，一定不是均衡(可靠的否證)。
- 贏多少不代表多接近均衡，只當參考資訊。call_station 只用抽象內的動作(check / call / pat),所以這個保證對它成立。
- Q4 的檢定力很低(連均勻亂打也會過);判斷「離均衡多遠」要靠可剝削度，也就是 SBR(第 11 節)。

目前 v1、v2 都沒通過(v1:Q1、Q3;v2:Q1、Q2、Q3)。這是預期中的：這套門檻是給 C1 正式解用的。

---

## 11. SBR 預算實驗(day49 設計，day50 結果：見 EXPERIMENT_LOG,(a)(b) 都被推翻，新的 (c) 成立)

**問題**:standard 預算下 SBR gain 是負的(response 在 held-out 牌上比 profile 還差)。可剝削度不可能是負的，所以這是量測問題。

**兩個假說**
- (a) **過擬合**:100 局學到的純策略 response 不能推廣。預測:gain 隨 response deals 增加而上升。
- (b) **fallback 偏差**(**[確認]** 程式碼層面):validation 遇到沒學過的狀態時,response 用 profile 機率最高的動作。策略是均勻或缺失時，最高機率是平手,`max` 取第一個合法動作：面對下注就是 **FOLD**,換牌就是 **pat**。v2 實際打到的 draw 決策有 46% 是均勻策略，這個偏差可能很大。預測:fallback 改成照 profile 抽樣時,gain 明顯高於 argmax 版本;argmax 版本的 gain 和「平手 fallback 比例」負相關。

**實驗**(`scripts/inspect_sbr_budget.py`,一次只變一個變數)
- 變數:response deals 100 / 300 / 1,000;其他固定(validation 1,000、sweeps ≤ 3、seed 2027、每個 seat 3 次)。
- 同一次 validation 裡另外跑一個 probe:只把 fallback 從 argmax 改成照 profile 抽樣，用**獨立 RNG**,所以 production 的數字和 `evaluate_checkpoint` 完全相同(`--check-report` 自動比對 100 局那一點)。probe 只在 script 裡,`solver/best_response.py` 的演算法沒改。
- 另外記錄 validation 中 responder 決策有多少來自 fallback、多少是平手 fallback(`best_response.py` 只加計數，固定 seed 前後輸出相同)。

**判讀**
- (b) 成立:每個預算下 sample gain 都比 argmax gain 高出好幾個 SE。
- (b) 不成立:兩者差距在 2 SE 內。
- (a) 成立:argmax、sample 兩者都隨預算上升。
- 兩者都不成立(1,000 局、sample 版本仍 ≤ 0):問題在別處(例如每個 sweep 重設 action value 造成的震盪，已知限制，**不重試**跨 sweep 累積)，回報再決定。

**之後的決定(需要你核准，屬演算法改動)**:如果 (b) 成立，提案把 `SampledBestResponse` 的 fallback 改成照 profile 抽樣。這樣 response 只在學過的狀態偏離 profile,gain 才是「可剝削度的下界估計」,SBR 才可能當門檻用。

### 11.1 結果(day50)
- (a) 過擬合：**推翻**。response deals 從 100 加到 1,000(10 倍),兩個 seat 平均 gain 是 +0.06 / −0.20 / +0.02,沒有上升。
- (b) fallback 偏差：**推翻**，而且方向相反。照 profile 抽樣不比 argmax 好(seat 1 九次全部更差，平均 −0.57)。
- (c) **樣本不足(新增，已確認)**:每個學到的狀態每個 sweep 平均只被看過 0.44–0.53 次，94–97% 的狀態最多 1 次。學到的狀態數和局數幾乎成正比，所以加局數只會增加狀態，不會增加每個狀態的樣本。SBR 等於用單一樣本挑純策略，拿去取代 profile 的混合策略。
- 結論：**目前的 SBR 在任何負擔得起的預算下都量不出可剝削度。** 報告繼續列出，但不設門檻，視為「不確定」。

---

## 12. 可剝削度估計的提案(待你核准，屬演算法層面)

A2 現在有可重現的報告和門檻，但缺一個可信的「離均衡多遠」指標，這是 GTO 產品最關鍵的數字。三個選項:

| | 做法 | 優點 | 缺點 / 風險 | 工作量 [推測] |
|---|---|---|---|---|
| **A(建議先做)粗分組 SBR** | response 不再對每個 info set 各學一個動作，而是對「(public node, 粗手牌強度級別,約 8–16 級)」學一個動作;沒學到的照 profile 抽樣 | 沿用現有 SBR 架構;粗分組的 response 仍是合法策略(只用了較少資訊),所以 gain 仍是**可剝削度的下界**;每組樣本數隨局數增加 | 下界可能偏鬆:只抓得到「整類手牌都犯的錯」(例如整體過度 fold) | 小:`best_response.py` 加一個分組參數 + 測試 |
| B Local Best Response(LBR,Lisý & Bowling 2017) | 每個決策點用對手 range(依 profile 做 Bayes 更新)估計各動作的期望值，取最大;不學習 | 大型撲克遊戲的標準下界方法;沒有樣本不足問題 | 需要對手 range 追蹤(換牌讓 range 轉移變複雜，repo 有 `draw_range_transition` 可用);運算量大 | 中到大 |
| C 精確 best response | 在抽象遊戲上走完整棵 public tree,用 range 向量算最佳回應 | 真正的可剝削度(在抽象內) | Python 下以 v2 的規模(約 200 萬 info set、換牌機會節點)很可能跑不動;要先估算 | 大 |

**不論選哪個，都先過「檢測力測試」**:做一個已知可被剝削的 profile(例如某個 seat 面對加注永遠 fold),估計器必須量到顯著為正的 gain;同時對 checkpoint 自己 vs 自己要量到接近 0。過不了就代表估計器本身不可信。目前的 SBR 我建議也補跑這個測試，確認它到底能不能偵測明顯的漏洞。

**選項 A 的驗證計畫**
- 處理的問題：樣本不足(11.1 的 (c))。
- 為什麼應該有效：分組後每組的樣本數隨局數線性成長;粗分組 response 是合法策略，所以 gain 在期望上 ≥ 0 才合理(若仍顯著為負，代表實作或評估有錯)。
- 怎麼測：檢測力測試 + v1 上 response deals 100 / 300 / 1,000,看 gain 是否 ≥ 0 且隨局數收斂、標準差下降。
- 什麼結果推翻它：檢測力測試量不到明顯漏洞，或 gain 仍隨機正負、不隨局數穩定。

### 12.1 檢測力測試與選項 A 的實作(day51,使用者核准選項 A)

**實作**
- `solver/best_response.py`:`SampledBestResponse` 新增可選參數 `response_grouping`。給了以後，每組資訊狀態只學一個動作;沒學到的地方照 profile 的混合策略打(訓練時用列舉出的各動作值按 profile 機率加權，validation 時照 profile 抽樣)。**不給時行為完全不變**(固定 seed 的 `inspect_sampled_best_response` 輸出改動前後逐字相同)。沒有做跨 sweep 累積(CLAUDE.md 禁止重試)。
- `solver/response_grouping.py`:`coarse_grouping(state, actions) = (seat, public node, 粗手牌級別, actions)`。postdraw:128 個 bucket 每 8 個一級(16 級);predraw / draw:由 `DrawHandBucket` 分約 20 級(順子或同花 / 無對子:最大牌級別 × 低牌張數 / 一對：未成對的低牌張數 / 兩對以上)。只用 responder 自己的資訊，所以分組 response 是合法策略,gain 是可剝削度的下界。
- `solver/exploitability_power.py`:植入漏洞「漏洞那一方面對下注時額外以機率 p fold」,以及手寫的參考 exploit(能加注就用最小加注，否則照 profile)。只改有存的策略;沒存的狀態仍是均勻，所以覆蓋率低的 checkpoint 實際漏洞較小。
- `scripts/inspect_sbr_power.py`:p = 0 / 0.1 / 0.3 / 1 × 兩種模式(`per_state` 原版、`grouped`)× 兩個 responder seat × 每格 2 次;所有格子共用同一批 validation 牌(common random numbers)。
- `scripts/inspect_sbr_budget.py` 加 `--grouping coarse`,通過檢測力測試後用來跑分組版本的預算曲線。

**預先登記的通過條件**(每個模式、每個 seat,`judge_estimator`)
- P1 檢測力：最大漏洞時，平均 gain > 2 SE,且 ≥ 參考 exploit gain 的 50%。
- P2 單調：漏洞變大時，gain 下降不超過 2 SE。
- P3 有效性：沒有漏洞時，gain ≥ −2 SE(合法 response 期望不會比 profile 差)。
- SE 用每次執行的 SE 平均(保守：同一批 validation 牌，重複之間誤差相關)。

**更正**:第 12 節原本寫「checkpoint 自己對自己要量到接近 0」是錯的：最佳回應對非均衡策略本來就該是正的。正確的對照是 P3:不能顯著為負。

**冒煙測試(container,40 次迭代的小 checkpoint,p = 1,seat 0,100 局 / 300 局 validation)**:參考 exploit +1.96 ± 0.58;原版 SBR −0.50 ± 0.42(找不到這麼明顯的漏洞);分組 SBR +0.97 ± 0.48(約參考值的 49%),fallback 5%。只是一次執行，不是結論，正式結果等 v1 的檢測力測試。

**判讀**
- 分組版 P1–P3 全過、原版沒過 → 分組 SBR 取代原版當可剝削度指標，接著跑分組版的預算曲線(gain 應 ≥ 0 且隨局數穩定),再決定是否設門檻。
- 兩者都沒過 → SBR 這條路放棄，改評估選項 B(LBR)。

### 12.2 結果與決定(day52–53)
- 檢測力測試(v1,300 局 response、1,000 局 validation):**分組 SBR 兩個 seat 都通過 P0–P3**,完全漏洞時比手寫 exploit 還強(seat 0:+1.70 vs +0.75;seat 1:+3.13 vs +1.98)。原版 SBR:seat 0 勉強通過(參考值的 51%),seat 1 失敗(16%)。
- 第一次 seat 1 的測試設計錯誤(漏洞包含開局面對大盲注的 fold,leak = 1 時 seat 1 根本沒有行動機會),day52 已修正並加上 P0 檢查。
- 限制:0.1 / 0.3 的小漏洞在 1,000 局 validation 下偵測不到(每次 SE 約 0.35–0.39)。
- **決定**:`evaluate_checkpoint` 的 SBR 預設改用分組版(`--sbr-grouping coarse`,report version 2)。用 `none` 的報告不算正式 benchmark。
- **下一步**:分組版的預算曲線(response deals 100 / 300 / 1,000)決定 standard preset 的 response deals 和是否設 SBR 門檻;之後重產 v1 / v2 的 standard 報告。
