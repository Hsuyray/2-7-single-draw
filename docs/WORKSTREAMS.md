# 工作拆分(Workstreams):從 CFR solver 到 GTO Wizard 類產品

用途：每個 workstream(WS)對應一個獨立的 context window / Claude session。開新 session 時，把該 WS 的「開場 prompt」貼進去即可。

依據:`main` @ `ff30393`(day31),含 `experiments/memory_profile/` 的實測數據;第 1 節有 A1(day35)與 A2 / B2(day56)的更新段落，較新的段落取代較舊的說法。標 **[推測]** 的是推論，不是實測。

---

## 0. 先講清楚兩個拆法的限制

**1. 2-7 Single Draw 沒有 preflop / postflop。** 對應的是三個 phase:`predraw_betting` → `draw`(換牌)→ `postdraw_betting`。下面用這三個名字。

**2. 「按 phase 拆」只適用於部分工作。** CFR 是在**一整棵遊戲樹**上同時解的:predraw 的策略取決於 postdraw 的價值，反之亦然。所以:
- **可以按 phase 拆的**:抽象化(bucket)設計、診斷、sanity check、UI 顯示。
- **不能按 phase 拆的**:訓練本身。任何一個 phase 的抽象化或 key 改了，整棵樹都要重新訓練,checkpoint 也要換版本。
- 因此 phase 類的 WS(B1–B3)可以平行**分析和提案**,但**改 code 要排隊**,一次只合併一個，合併後重新訓練、重新評估。

**3. 「range 跟 action 拆」是對的，而且是產品層最自然的切法**:
- **action 側** = 行動抽象(下注尺寸、換牌動作)與每個節點的動作頻率(WS B4、D1)。
- **range 側** = 每個節點雙方手牌分佈的傳遞、EV、以及 2-7 手牌的分類顯示(WS D2、D3)。

---

## 1. 目前狀態(實測，給每個 WS 當背景)

**P0 profiling**:`max_draw=5`,bucket,fast,seed 42,`--no-tracemalloc`,在你的筆電上跑 1,000 次迭代:

| 指標 | 數值 |
|---|---|
| 速度 | 約 0.59 秒/迭代(1,000 次 590.8 秒) |
| 節點數 | 114,110 |
| RSS | 0.465 GB,存檔後 0.550 GB,存檔暫時多吃約 0.085 GB |
| 每節點記憶體 | 約 3.9 KB(RSS 增量 ÷ 節點數) |
| 節點組成 | postdraw 94,702(83%)、draw 16,069(14%,每個節點 32 個換牌動作)、predraw 3,339(3%) |
| 成長形狀 | **次線性，還沒飽和**。前 50 次 +11,386 節點，最後 50 次 +3,940 |

**tracemalloc**(300 次迭代)留存記憶體前幾名:
- `copy.py` 42 MiB(`deepcopy` 產生的物件在訓練結束後**仍被引用**,值得查)
- `cfr_node.py` 40.7 MiB(每節點兩個 dict)
- `public_state.py` 26.4 MiB(key)
- `bucket_hand_codec.py` 25.4 MiB(第 98–99 行)

**更新(A1,day35)**:節點數有確定上限,`fast` 約 34.6 萬、`full` 約 203 萬;8k 的 `full` checkpoint 已有 1,068,645 個資訊集,且其 metadata 顯示用的是 `full` 下注比例。碎片化已排除。詳見 `docs/A1_REPORT.md`。下面這段是 A1 之前的推估,其中「節點數可能到 50 萬以上」「碎片化未排除」已被取代。

**更新(A2 / B2,day56)**:
- **評估基準**:`python -m scripts.evaluate_checkpoint <checkpoint>`(preset `standard`)是所有策略品質判斷的共同尺，報告含門檻判定(gates v2),可跨平台逐位重現。用法、指標與限制見 `docs/A2_DESIGN.md` 第 13 節。
- **v1**:覆蓋率 96.8%,實際打到時是均勻策略 11–23%,可剝削度下界(分組 SBR)每局 +1.57 chips,門檻 FAIL。**v2**(8k、`max_draw=5`):覆蓋率 92.8%,draw 實際打到時 46% 是均勻策略，下界每局 +2.47 chips,門檻 FAIL。
- 以前的「v1 約 98%、v2 約 94% 覆蓋率」已被取代：舊的覆蓋率 script 讓 button 交替 0 / 1(day45 已修)。
- **目前的主要瓶頸是訓練不足**(已存策略 70–93% 是均勻的);正確性檢查(動作空間一致、零和、換牌對應、`draw_count` 編碼、重現性)都通過。
- **button 位置**:訓練只用 `button_seat=0`,而 key 存絕對 button,所以 button 1 的查詢全部查不到。遊戲對座位對稱，要靠 player-relative key 或查詢層的座位對調解決(D1 / 凍結介面)，不是多訓練。
- **行動順序**(程式碼確認):predraw button 先;換牌大盲先換、button 後換(看得到大盲換幾張);postdraw 大盲先行動。
- 下一步依第 2 節的順序：先 C1(可續跑訓練與解庫),再依 A2 的評估一次合併一個 B 的改動。

**推估 [推測]**(A1 之前，已被上面兩段取代):
- **40k 次的時間**:約 6–7 小時。
- **40k 次的記憶體**:節點數如果到 50 萬以上，乘 3.9 KB/節點就是 2 GB 以上，和「40k 跑爆 2 GB」吻合。看起來比較像**合理但很大的狀態空間 + 每節點太胖**,不像無上限的 cache 洩漏。但 float key 造成的碎片化(fragmentation)還沒排除，這正是你新增的 `scripts/inspect_node_composition.py` 要回答的。

**已經有的產品層元件**(`solver/`):
- `StrategyBrowser`(hand / range snapshot、`apply_betting` / `apply_draw`)
- `PublicNodeNavigator`、`RangeTracker`、`range_view`、`draw_range_transition`
- `checkpoint_browser`、`scripts/query_strategy_checkpoint.py`

**還沒有的**:
- **EV**:整個 repo 沒有 EV 計算。checkpoint 只存平均策略，沒有 regret、沒有 value。
- **UI**:沒有任何前端。
- **2–6 人**:trainer 只支援單挑。

---

## 2. Workstream 總覽與相依關係

| ID | 名稱 | 類型 | 前置條件 | 可平行? |
|---|---|---|---|---|
| A0 | Repo 整理與共用規則 | 基礎 | 無 | 最先做，很短 |
| A1 | 記憶體與規模(P0) | 基礎 | A0 | 和 A2 平行 |
| A2 | 評估工具(收斂 / 可剝削度 / 覆蓋率) | 基礎 | A0 | 和 A1 平行 |
| B1 | Predraw 策略品質 | 抽象 / phase | A2 | 分析可平行;改 code 要排隊 |
| B2 | Draw(換牌)策略品質 | 抽象 / phase | A2 | 同上 |
| B3 | Postdraw 策略品質 | 抽象 / phase | A1、A2 | 同上(節點最多，和 A1 高度相關) |
| B4 | 行動抽象(下注尺寸) | 抽象 / action | A2 | 同上 |
| C1 | 正式訓練流程與解庫(solution library) | 求解 | A1、A2 | 有一版穩定抽象後 |
| C2 | 多核心 | 求解 | A1、C1 | 最後 |
| D1 | Solution 資料格式與查詢 API(action 側) | 產品資料 | A0 | 可以早做，先用現有 v2 checkpoint |
| D2 | Range 傳遞與 EV(range 側) | 產品資料 | D1 | D1 的 API 定了之後 |
| D3 | 2-7 手牌分類與顯示格(取代 13×13) | 產品設計 | 無 | 隨時，完全獨立 |
| E1 | Solution browser 網頁(核心產品) | UI | D1 的 API 格式(可以先用 mock) | 和 A1/A2 平行 |
| E2 | Practice / Trainer 模式 | UI | E1、D2 | 後期 |
| E3 | 進階:aggregate reports、多人桌、手牌紀錄分析 | UI / 求解 | E1、C1 | 最後 |

**建議順序:**
1. **第一波(現在)**:A0 → 再同時開 A1、A2、D3、D1。
2. **第二波**:B1–B4 分析提案(平行),E1 用 mock 資料開工。
3. **第三波**:依 A2 的評估結果，一次合併一個 B 的改動並重新訓練 → C1 產出第一個正式解 → D2。
4. **第四波**:E1 接真實資料 → E2 → C2 / E3。

---

## 3. 共用規則(每個 session 都要遵守)

1. **規則來源**:先讀 `CLAUDE.md`(A0 會建立，內容 = 原本的 handoff 文件)和本文件中自己那一節。
2. **檔案所有權**:只改自己 WS 擁有的檔案;其他 WS 的檔案只讀。要改別人的檔案，就寫成提案放在 `docs/proposals/<WS>-<主題>.md`。
3. **凍結介面**(改了會影響所有人，只能由指定的 WS 改，而且要升版本):
   - `InformationState` / `PublicNodeKey` 的 key 格式，以及 checkpoint schema(目前 v3)→ 只能由 A1 或 B 系列改，一次一個;改了就重新訓練，並升 `CHECKPOINT_FORMAT_VERSION`。
   - 查詢 API 的 JSON 格式 → D1 擁有。
   - 手牌分類(hand class taxonomy)→ D3 擁有。
4. **分支**:每個 WS 用自己的 branch,例如 `ws-a1-memory`,commit 用 day 編號。
5. **證據**:沿用 handoff 規則：固定 seed,一次只改一個變數。行為不變的改動要附 before/after 等價證明(節點數、策略都一樣)。
6. **紀錄**:實驗結果寫進 `docs/EXPERIMENT_LOG.md`;每個 session 結束前更新本文件中自己那節的「狀態」。

---

## 4. 各 Workstream 詳細內容

每節格式：目標 / 擁有的檔案 / 只讀 / 產出 / 完成條件 / 不要做 / 開場 prompt。

### A0. Repo 整理與共用規則

- **目標**:讓之後每個 session 的 diff 乾淨，規則自動載入。day31 的 commit 混進大量 `.pyc`,就是要解決的問題。
- **擁有**:`.gitignore`、`requirements.txt`、`CLAUDE.md`(新增)。
- **產出**:
  1. `.gitignore` 加入 `.venv/`、`__pycache__/`、`*.pyc`、`*.tmp`、`experiments/**/*.chk.gz`。
  2. `requirements.txt` 至少寫入 `psutil`、`pytest`。
  3. `CLAUDE.md` = handoff 文件內容 + 指向本文件。
  4. 解除追蹤 `.venv`、`__pycache__` 的指令清單。用 `git rm --cached`,由你決定要不要執行。
  5. checkpoints 的去向建議:Git LFS 或 GitHub Releases。
- **完成條件**:`git status` 在跑完測試後是乾淨的。
- **不要做**:改寫 git 歷史、刪除 checkpoint 實體檔案。
- **開場 prompt**:
  > 讀 docs/WORKSTREAMS.md 的 A0 節，執行 A0。不要刪除任何檔案實體，不要改寫歷史;需要 git rm --cached 的部分只列指令讓我決定。

### A1. 記憶體與規模(P0)

- **目標**:回答「40k 次為什麼爆、要多少記憶體才夠」,再決定要不要優化、怎麼優化。
- **擁有**:`scripts/profile_memory.py`、`scripts/inspect_node_composition.py`、`solver/memory_guard.py`。核准後也可改 `solver/cfr_node.py`、`solver/node_store.py`。
- **只讀**:`cfr_trainer.py`、`public_state.py`、`information_state.py`(要改時寫提案)。
- **要回答的問題(依序)**:
  1. **碎片化**:同一個 `action_history` 是否對應到多個 `pot` / `stack` 浮點值?用 `inspect_node_composition.py` 跑 `experiments/p0_small.chk.gz`,看「distinct public nodes」和「distinct history keys」差多少。
  2. **`copy.py` 的 42 MiB**:`deepcopy` 產生的物件為什麼在訓練後還活著，是被 node 的 key 或 actions 引用嗎?
  3. **`bucket_hand_codec.py:98–99`**:這兩行建立了什麼、存在哪裡?
  4. **飽和點**:用 2k / 4k / 8k 次迭代畫出「節點數 vs 迭代」,外推 40k 的節點數和 RSS。
- **產出**:記憶體模型(每節點 bytes、各結構佔比、40k 的預測);每個候選優化(`__slots__`、陣列存 regret、key interning、修正碎片化)的預期節省量。
- **完成條件**:有證據支持的單一下一步。如果要動 key,轉交給凍結介面流程。
- **不要做**:沒有量測就優化;改 CFR 數學。
- **開場 prompt**:
  > 讀 CLAUDE.md 和 docs/WORKSTREAMS.md 的 A1 節與第 1 節的實測數據。依序回答 A1 的四個問題;每個問題先寫診斷方法和「什麼結果會推翻假設」,再寫要我跑的指令。不要改 CFR 邏輯。

### A2. 評估工具(所有策略品質判斷的基準)

- **目標**:一套固定 seed、可重複的評估，讓 B / C 系列的每個改動都能用同一把尺比較。
- **擁有**:`scripts/evaluate_strategy_profile.py`、`scripts/inspect_*convergence*.py`、`scripts/inspect_*coverage*.py`、`solver/strategy_profile_evaluator.py`;`solver/best_response.py` 只能做非演算法的改動(SBR 跨 sweep 累積已試過並還原，不要重試)。**例外**:分組 SBR(`response_grouping`)是使用者 day51 核准的演算法改動，不加 grouping 時行為與原版逐位相同。A2 另外新增並擁有 `scripts/evaluate_checkpoint.py`、`solver/checkpoint_evaluation.py`、`solver/benchmark_gates.py`、`solver/response_grouping.py`、`solver/exploitability_power.py`、`scripts/inspect_sbr_budget.py`、`scripts/inspect_sbr_power.py` 及對應測試。
- **產出**:一個 `scripts/evaluate_checkpoint.py`(或整合現有的 script),一次輸出:
  - 各 phase 覆蓋率，以及加權後的缺失狀態(依 reach 排序)
  - current-vs-average 距離
  - SBR proxy(附 response-deal 數量和變異)
  - 對固定對手的 baseline、和前一版 checkpoint 的 head-to-head
- **完成條件**:同一個 checkpoint 跑兩次結果一致;v1 和 v2 都有一份基準報告存在 `experiments/eval/`。
- **開場 prompt**:
  > 讀 CLAUDE.md 和 docs/WORKSTREAMS.md 的 A2 節。先盤點現有的 evaluate / inspect script 各自量什麼、重複什麼，再提出單一評估入口的設計;實作前先給我看設計。

### B1. Predraw 策略品質

- **範圍**:`predraw_betting` 的節點(目前約佔 3%,但是 reach 最高)。
- **重點**:
  - 第一個決策點的缺失(歷史數據：在 pot 4.5 / bet 2.0 / 歷史長度 0 缺 226 個)。
  - `DrawHandBucket` 是否把策略上不同的手牌合併了。例如同樣是 4 張低牌，抽 7 和抽 8。
  - 先手 / 後手的策略合不合理(pat 手是否加注、垃圾牌是否棄牌)。
- **擁有**:`docs/proposals/B1-*.md`、`tests/test_predraw_*`(新增)。`draw_hand_bucket.py` 要改時走凍結介面流程。
- **產出**:predraw sanity 報告(一組代表性手牌的動作頻率表)、bucket 分裂 / 合併提案和預期影響。
- **開場 prompt**:
  > 讀 CLAUDE.md、docs/WORKSTREAMS.md 第 0 節與 B1 節。用現有 checkpoint 和 StrategyBrowser 做 predraw 的 sanity 分析;只寫分析和提案，不要改 bucket 或 key 的 code。

### B2. Draw(換牌)策略品質

- **範圍**:`draw` 節點(每個 32 個動作 = 所有換牌組合)。
- **重點**:
  - 換牌動作在 bucket 標準順序和原始牌順序之間的對應是否正確(`draw_bucket_card_ordering`、`strategy_browser_discard_mapping` 測試)。
  - 明顯錯誤的換牌(拆掉 pat 7-low、保留對子)出現的頻率。
  - 換幾張是公開資訊，會進入 postdraw 的 key:`draw_count` 在 key 中的編碼是否一致。
  - 32 個動作裡很多是明顯劣勢，是否可以安全地縮減(只能當 ablation,不保證行為不變)。
- **擁有**(day56,比照 B1 的假設，使用者未另行指定):`docs/proposals/B2-*.md`、`tests/test_draw_mapping_properties.py`、`tests/test_draw_equity_oracle.py`、`scripts/inspect_draw_decisions.py`、`scripts/inspect_draw_equity.py`(皆為唯讀分析，不改 solver)。
- **產出**:換牌 sanity 報告、動作縮減 ablation 提案。
- **開場 prompt**:
  > 讀 CLAUDE.md、docs/WORKSTREAMS.md 第 0 節與 B2 節。驗證換牌動作對應的正確性，並用現有 checkpoint 分析換牌決策;只寫分析和提案。

### B3. Postdraw 策略品質

- **範圍**:`postdraw_betting` 節點，佔 83%,是記憶體和收斂的主戰場。
- **重點**:
  - 128 個 `PostdrawStrengthBucket` 夠不夠細、會不會太細(ablation:64 / 128 / 256)。
  - 節點為什麼這麼多：是 bucket 數 × 下注歷史 × 雙方換牌數 × 浮點 pot 碎片化?要和 A1 的問題 1 一起看。
  - 有沒有完全相同的 bucket 卻出現不同 key 的情況。
- **前置**:A1 回答碎片化問題之後。
- **產出**:postdraw 節點組成分析、bucket 數 ablation 的實驗設計。
- **開場 prompt**:
  > 讀 CLAUDE.md、docs/WORKSTREAMS.md 第 0、1 節與 B3 節，以及 A1 的結論。分析 postdraw 節點的組成，設計 bucket 數 ablation;不要改 code。

### B4. 行動抽象(下注尺寸)

- **範圍**:`bet_sizing.py`、`bet_sizing_profiles.py`(`FAST` / `FULL`,`chip_increment=0.1`,`all_in_threshold=0.90`)。
- **重點**:
  - fast 和 full 的策略差異、節點數差異、對 EV 的影響。
  - `chip_increment=0.1` 的四捨五入和 float key 碎片化的關係(和 A1 有關)。
  - 產品要顯示的尺寸。GTO Wizard 會顯示具體的 bb 數字。
- **產出**:尺寸 ablation 設計、建議的正式尺寸組合。
- **開場 prompt**:
  > 讀 CLAUDE.md、docs/WORKSTREAMS.md 的 B4 節。比較 fast / full 下注抽象的設計與已知數據，設計 ablation;不要改 bet_sizing 的 code。

### C1. 正式訓練流程與解庫

- **目標**:像 GTO Wizard 一樣，有一個「解庫」,每個遊戲設定(人數、有效籌碼深度)一份正式解。
- **擁有**:`scripts/save_training_checkpoint.py`、新增的 `scripts/solve_library.py`、`solutions/manifest.json`(或類似的檔案)。
- **產出**:
  1. 設定矩陣：先做單挑 × {10, 20, 30, 50, 100} bb,實際深度由你決定。
  2. 每份解的 metadata:config、seed、迭代數、時間、節點數、峰值 RSS、A2 評估報告。
  3. 可以中斷、續跑的長時間訓練。checkpoint 要另外存 regret / strategy sum;這會改 schema,需要升版本。
- **前置**:A1(記憶體夠跑)、A2(知道多少迭代算「夠」)。
- **開場 prompt**:
  > 讀 CLAUDE.md、docs/WORKSTREAMS.md 的 C1 節、A1 和 A2 的結論。設計解庫與可續跑訓練(含 checkpoint schema 變更的提案);實作前先給我看設計。

### C2. 多核心

- 依照 `docs/PARALLEL_TRAINING_DESIGN.md`:先做 Option D(平行跑獨立的實驗 / 評估),再考慮 Option B。
- **前置**:A1、C1。需要你核准才實作。

### D1. Solution 資料格式與查詢 API(action 側)

- **目標**:產品後端。給定(設定、行動路徑、手牌或 range),回傳每個動作的頻率。
- **擁有**:新增的 `product/api/`(或 `server/`)、`docs/API.md`。
- **只讀**:`strategy_browser.py`、`checkpoint_browser.py`、`public_node_navigator.py`(要改時寫提案)。
- **產出**:
  1. `docs/API.md`:JSON 格式(節點、合法動作和標籤、每手牌 / 每 bucket 的頻率、range 匯總)。這是凍結介面,E1 依賴它。
  2. 用 FastAPI(或其他)包裝 `StrategyBrowser` 的唯讀 API。
  3. 服務用的預先計算格式：把 checkpoint 轉成「每個公開節點一張表」,讓查詢不必每次載入 59 MB 的 pickle。
  4. 一份可以給 E1 直接使用的 mock JSON。
- **完成條件**:用現有 v2 checkpoint 能從根節點一路查到 postdraw。
- **開場 prompt**:
  > 讀 CLAUDE.md、docs/WORKSTREAMS.md 的 D1 節。先讀 strategy_browser.py、checkpoint_browser.py、public_node_navigator.py,寫出 docs/API.md 草案(含 mock JSON)給我審;審過再實作。

### D2. Range 傳遞與 EV(range 側)

- **目標**:GTO Wizard 的核心數字：每個節點雙方的 range(權重)、每手牌和每個動作的 EV、equity。
- **擁有**:新增的 `solver/strategy_values.py`(或類似的檔案)、`scripts/compute_node_values.py`。
- **重點**:
  - 用平均策略做 range 傳遞，包括換牌造成的 range 轉換(`draw_range_transition`)。
  - EV 要額外跑一次評估遍歷，而且只對平均策略算。這是新的計算，和訓練分開，結果存成另外的檔案。
  - bucket 抽象下，同一個 bucket 內不同的實際手牌策略相同，但 EV 不同;要決定 EV 報在 bucket 層級還是實際手牌層級。
- **前置**:D1 的格式。
- **開場 prompt**:
  > 讀 CLAUDE.md、docs/WORKSTREAMS.md 的 D2 節和 docs/API.md。設計 range 傳遞與 EV 計算(含成本估計、在 bucket 抽象下的定義);實作前先給我看設計。

### D3. 2-7 手牌分類與顯示格(取代德州撲克的 13×13)

- **目標**:定義產品裡的「range grid」。2-7 是 5 張牌的 lowball,沒有 13×13 的現成格子。
- **擁有**:`docs/HAND_TAXONOMY.md`、新增的 `solver/hand_classes.py`(純函式，不碰訓練)。
- **產出(提案)**:
  - **pat 手**:依最高牌 / 第二高牌分格，例如 7-5、8-6、9-x、T-x、對子以上。
  - **一張換牌手**:依保留 4 張的最高牌分格，例如「抽 7(2345 / 2346 / ...)」、「抽 8」。
  - **兩張以上換牌**:粗分。
  - 每格可以展開成具體的牌型、組合數，並說明和 `DrawHandBucket` / `PostdrawStrengthBucket` 的對應。
- **完成條件**:每一手 5 張牌都恰好落在一格(要有測試);你確認分類符合職業玩家的習慣。
- **開場 prompt**:
  > 讀 docs/WORKSTREAMS.md 的 D3 節和 docs/game_rules.md。提出 2-7 Single Draw 的手牌分類方案(predraw 與 postdraw 各一套)給我審，附每格的組合數;不要改 solver 現有的檔案。

### E1. Solution browser 網頁(核心產品)

- **目標**:GTO Wizard 的「Study」模式。
- **畫面**:
  - 選擇遊戲設定(籌碼深度)
  - 行動路徑導覽(預設是 predraw → draw → postdraw 的樹)
  - range grid(用 D3 的分類，顏色代表動作比例)
  - 單手牌的詳細資訊(動作頻率，有 EV 時加上 EV)
  - 換牌畫面(顯示換哪幾張)
- **擁有**:新增的 `frontend/`。
- **前置**:D1 的 `docs/API.md` 和 mock JSON,可以完全不等 solver。
- **開場 prompt**:
  > 讀 docs/WORKSTREAMS.md 的 E1 節和 docs/API.md(含 mock JSON)。先提出技術選型和畫面結構;確認後只用 mock 資料實作 Study 頁面，不要碰 solver/。

### E2. Practice / Trainer 模式

- 對 GTO 策略實際打牌，每個決策根據頻率和 EV 損失打分。
- **前置**:E1、D2(打分需要 EV)。

### E3. 進階功能

- **Aggregate reports**:所有 predraw 開局情境的總表。
- **多人桌**:2–6 人，需要新的 trainer 和大量算力，最晚做。
- **手牌紀錄分析**:上傳實戰紀錄後和解比較。

---

## 5. 「完成」的定義(最終產品)

1. **解庫**:至少一組單挑、`max_draw=5`、多個籌碼深度的正式解，每份都附 A2 評估報告且通過門檻(門檻由 A2 提出、你核准)。
2. **網頁**:可以選擇深度，在三個 phase 之間導覽，看到 range grid、單手牌頻率和 EV、換牌建議。
3. **Practice 模式**:可以打牌並得到評分。
4. **文件**:API、手牌分類、每份解的設定與限制(例如 bucket 抽象造成的誤差)寫清楚。

---

## 6. 各 WS 狀態(每個 session 結束前更新)

| ID | 狀態 | 最後更新 | 分支 | 備註 |
|---|---|---|---|---|
| A0 | 已完成,待你執行 `docs/A0_UNTRACK_COMMANDS.md` 的解除追蹤指令 | day33 | `ws-a0-repo-hygiene` | 新增 `.gitignore`、`requirements.txt`、`CLAUDE.md`;尚未執行任何 `git rm --cached` |
| A1 | **完成**:interning 實測通過(存檔前 RSS -70%,存檔峰值 -62%),3.12 指紋前後相同;已合併進 `main`(PR #6) | day42 | `ws-a1-memory` | `full` 40k 預估峰值約 4 GiB、約 14 小時;後續候選(不急):存檔串流化、dict 改陣列 |
| A2 | **完成**:單一評估入口 `scripts/evaluate_checkpoint.py`、門檻 gates v2(含 Q6)、分組 SBR(通過檢測力測試);v1 / v2 standard 報告(report v2)在 `experiments/eval/`,跨平台逐位重現 | day56 | `claude/lucid-ritchie-myhksz` | v1 下界 +1.57、v2 +2.47 chips/局，兩者都 FAIL;限制與用法見 `docs/A2_DESIGN.md` 第 13 節 |
| B1 | 未開始 | | | |
| B2 | **完成**(分析與提案):換牌對應與 `draw_count` 編碼正確;v1 / v2 換牌錯誤分析完成(v2:53% 的 draw 決策未訓練，已訓練的也接近均勻);提案 P1–P3 在 `docs/proposals/B2-draw-analysis.md`,等 C1 後再排;選項價值分析延後給 A2 的通用 LBR | day59 | `claude/lucid-ritchie-myhksz` | 擁有見 B2 節;對 A2 提了「離均勻距離」指標 |
| B3 | 未開始 | | | |
| B4 | 未開始 | | | |
| C1 | **設計待核准**:`docs/C1_DESIGN.md`(訓練 script 盤點、可續跑訓練、解庫、單一訓練入口)。原型確認 pickle 整個 trainer 後續跑與連續訓練指紋相同 | day59 | `claude/sleepy-mendel-dpgv70` | 尚未改程式碼;待決事項見設計第 6 節 |
| C2 | 未開始 | | | |
| D1 | 未開始 | | | |
| D2 | 未開始 | | | |
| D3 | 未開始 | | | |
| E1 | 未開始 | | | |
| E2 | 未開始 | | | |
| E3 | 未開始 | | | |
