# 提案:draw 節點的換牌動作抽樣(day76)

標記:**[確認]** = 已用程式或實測驗證;**[推測]** = 推論。

## 1. 問題:draw 階段的更新為什麼少 [確認]

雲端診斷：fast sizing、`max_draw=5`、bucket、simple averaging、seed 42,2,000 次迭代(1,164 s),直接讀 trainer 的節點計數。draw 分成先換(大盲)和後換(button,看得到大盲換幾張):

| 階段 | 節點 | public 節點 | 手牌 bucket | 動作數 | regret 更新 / 迭代 | 每次迭代的子樹展開 |
|---|---|---|---|---|---|---|
| predraw | 7,728 | 20 | 789 | 2–5 | 4.3 | 14 |
| draw(先換) | 5,353 | 19 | 592 | **32** | 2.0 | 64 |
| draw(後換) | 17,051 | 114 | 603 | **32** | 3.9 | 124 |
| postdraw | 186,842 | 3,152 | 127 | 2–5 | 141 | 368 |

讀法:
- **每次迭代，每個 draw public 節點只更新一個手牌 bucket**(這一局發到的那手牌)。draw 每次迭代只有約 6 次 regret 更新，分散在 22,404 個狀態上;每個狀態每次迭代的更新數，draw 2.7e-4,postdraw 7.6e-4,predraw 5.6e-4。
- **後換的人 public 節點多 6 倍**:key 裡有對手換幾張(0–5)。這是真實資訊，不能合併。
- **draw 的每次更新都很貴**:traverser 在 draw 節點要把 32 個換牌都往下走完整棵 postdraw 子樹。每次迭代的 458 次節點拜訪裡，postdraw 佔 372,幾乎全部來自 traverser 這 32 個分支。
- 每個 draw 節點有 32 個動作，下注節點只有 2–5 個：同樣的更新次數，draw 要離開均勻更難。

所以「每次迭代的 draw 更新數」是結構決定的(一局一手牌);能改的是**每次迭代的成本**:成本幾乎都花在把 32 個換牌全部展開，其中大部分是明顯錯誤的換牌(B2:v2 已訓練的 draw 狀態仍有 4–28% 機率放在可避免的錯誤上)。

## 2. 修法:traverser 的 draw 節點只展開一部分換牌，重要性加權

`CFRTrainer.draw_action_sampling = k`(`--draw-action-sampling k`,預設 0 = 原本的行為)。只在 traverser 的 draw 節點:
- 每個換牌動作 a 獨立地以機率 q(a) = min(1, max(0.05, k·σ(a))) 展開(σ = 目前的 regret-matching 策略),平均約 k 個。
- 展開的動作:v̂(a) = v(a)/q(a);沒展開的:v̂(a) = 0。節點值 û = Σσ(a)v̂(a),regret r̂(a) = v̂(a) − û。
- 展開的子樹帶權重 1/q(a) 往下傳：子樹裡 traverser 的 regret 和對手節點的 simple averaging 累積都乘上它。

E[v̂(a)] = v(a),所以節點值、每個 regret、每個平均策略的累積量都是不偏的(和 external sampling 本身一樣是不偏估計，只是變異數較大)。下限 0.05 保證每個換牌都還會被探索；好的換牌(σ 大)幾乎每次都展開。

這是 Average Strategy Sampling(Gibson et al. 2012)的同類做法，改用目前策略決定展開機率，只用在動作最多的 draw 節點。

限制:
- 只能配 `--average-mode simple`:reach averaging 在 traverser 節點用 traverser 的 reach 累積，沒展開的分支會漏掉。
- checkpoint 格式(v3)和 key 不變。

## 3. 為什麼應該有用

draw 更新數 / 小時 = 每次迭代的更新數(不變)× 每小時迭代數。實測(雲端、fast sizing、300 次迭代、三個同時跑):

| k | 秒 | 節點 | 相對速度 |
|---|---|---|---|
| 0(原本) | 197 | 66,562 | 1× |
| 8 | 52 | 26,294 | 3.8× |
| 4 | 35 | 18,385 | 5.6× |

**[推測]** 同樣時間可以多跑約 4–5 倍迭代，所以 draw(和其他每個階段)的更新次數也多約 4–5 倍；代價是每次更新的雜訊變大。淨效果要靠實驗。節點變少是因為很少被選的換牌之後的 postdraw 狀態還沒建立;coverage 量的是實際打到的路徑，要看它有沒有變差。

## 4. 測試(`tests/test_draw_action_sampling.py`)

- 預設是 0;負數、reach averaging、full traversal 會被拒絕。
- k = 0 和原本的 trainer 指紋完全相同(預設路徑 sample_weight 永遠是 1.0,乘 1.0 是精確的)。
- 展開機率：上限 1、下限 0.05。
- **精確不偏**:對 4 個動作列舉所有展開 / 不展開的組合，期望的節點值和 regret 剛好等於精確值(3 組策略，含有 0 機率的動作)。
- **整條 traversal 不偏**:凍結學習(add_regrets / accumulate_strategy 不改節點),從同一個 draw 節點跑 100 次全部展開、1,000 次 k=4,draw 節點的值和 32 個 regret 的平均都在 4 個合併 SE 內。
- 開抽樣訓練 30 次：同 seed 結果相同、和不抽樣不同、所有平均策略加總為 1、沒有 NaN / inf、權重非負。
- C1:manifest `abstraction.draw_action_sampling`(沒有這個欄位 = 0),`training_argv` 會傳給訓練 script;非 0 時寫進 training state 的 config(換設定續跑會被拒絕)。

## 5. 實驗與推翻條件

fast sizing、`max_draw=5`、bucket、stack 20、seed 42、simple + uniform,和 day74 / day75 同一串牌局。k = 4,存 8k / 16k / 24k / 32k。基準 = day74 的 `avgmodes__simple__008000`(k = 0)。A2 `standard`、seed 2027。

比較兩種:
- **同樣時間**(主要):k = 4 中訓練時間最接近基準 8k 的 milestone。
- 同樣迭代數(8k):看每次迭代的品質損失有多大。

推翻條件(同樣時間):
- draw 的近均勻比例沒有比較低 → 不採用。
- SBR、對打、baselines 任何一項顯著變差(> 2 SE)→ 不採用，先找原因。
- coverage 明顯下降(> 1 個百分點)→ 不採用，先找原因。

## 6. 實驗結果(day76,雲端)

設定如第 5 節。訓練(雲端，和其他工作同時跑，時間只能粗略比較):
- k = 4:8k 838 s / 207,535 節點;16k 1,744 s;24k 2,668 s;32k 3,610 s / 365,807 節點。每次迭代快約 5.8 倍。
- 基準 k = 0:8k 4,833 s / 358,987 節點(和 day74 simple 8k 節點數相同;A2 報告的數字也和 day74 完全一樣)。

同樣時間取 k = 4 的 **32k**(3,610 s,比基準 8k 少約 25% 時間，對抽樣不利)。報告在 `experiments/draw_sampling/eval/`,對打 = `--previous` 基準 8k(正值 = k = 4 贏)。

| | 基準 k=0 8k | k=4 8k(同迭代) | **k=4 32k(同時間)** |
|---|---|---|---|
| 訓練秒數 | 4,833 | 838 | 3,610 |
| coverage | 94.73% | 92.64% | **98.13%** |
| 近均勻(實際打到;pre / draw / post) | 8.36 / 26.07 / 12.13% | 8.73 / 24.28 / 45.71% | **2.90 / 9.10 / 12.66%** |
| 有任何 miss 的牌局 | 14.49% | 19.51% | 5.92% |
| SBR mean(per-run SE 約 0.65) | 3.76 | 4.12 | **2.22** |
| vs uniform | +1.82 ± 0.12 | +1.05 ± 0.12 | +1.94 ± 0.12 |
| vs call_station | +0.73 ± 0.15 | +0.37 ± 0.15 | +0.37 ± 0.15 |
| 對打(vs 基準 8k) | | −0.81 ± 0.14 | −0.14 ± 0.14 |
| gates 失敗 | Q1 Q2 Q3 Q6 | Q1 Q2 Q3 Q6 | **Q3(只剩 postdraw)、Q6** |

讀法:
- **[確認] 同樣迭代數比較差**(SBR 較高、postdraw 近均勻 45.7%、對打 −0.81,約 6 SE):每次更新雜訊大，且很少被選的換牌之後的 postdraw 狀態還沒建立。這是預期的代價。
- **[確認] 同樣(更少)時間比較好**:draw 近均勻 26.1% → 9.1%,predraw 8.4% → 2.9%,postdraw 持平;coverage +3.4 個百分點，Q1、Q2 第一次通過;SBR 3.76 → 2.22(差 1.54,約 3 SE 以上)。
- vs uniform、對打：差異在 1 SE 內。
- **vs call_station 低了 0.37(約 1.8 SE)**:沒到推翻門檻(2 SE),但方向不好，要在下一次跑留意。**[推測]** 可能和 postdraw 近均勻沒有改善有關(call_station 只在下注節點有差)。

依第 5 節推翻條件：三條都沒有觸發 → **建議採用 k = 4**。

限制:
- 只有一個 seed、fast sizing、雲端計時(同時跑多個工作)。
- full sizing 的加速倍數沒量過:postdraw 子樹更大，加速應該不會更小 **[推測]**,但要在筆電上實測。
