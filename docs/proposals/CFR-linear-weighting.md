# Linear CFR weighting for external sampling(day75)

狀態：已實作為選項(`iteration_weighting`,預設 `uniform` = 原本的行為);實驗見第 6 節。前一項：`docs/proposals/CFR-average-weighting.md`(simple averaging,已採用)。

## 1. 現象 [確認，程式碼 + day71–73 數據]
目前每一次迭代的 regret 和平均策略貢獻權重相同。早期迭代的策略接近均勻、regret 來自亂打，但它們在 regret 累積和平均策略裡的份量和後期一樣。
- e70 32k:draw 階段每個節點的 regret 更新次數中位數只有 7(betting 23)。只被更新幾次的節點，早期的雜訊佔了很大比例。
- 32k 時實際打到的近均勻比例 draw 21%、postdraw 10.4%(Q3 FAIL)。

## 2. 修正(Brown & Sandholm 2019, Linear CFR)
第 t 次迭代(t = 1, 2, …)的 regret 和平均策略貢獻都乘上 t。等價於每次迭代後把既有的累積值乘 t/(t+1),但不用掃過所有節點，計算量不變。
- regret:`regret_sum += t · r`。
- 平均:`strategy_sum += t · w · σ`(`w` 是 average mode 原本的權重:simple 是 1,reach 是自己的到達機率)。
- Pluribus 在 MCCFR 裡用過同樣的線性折扣(Brown & Sandholm 2019, Science),所以和抽樣不衝突。
- 數值：累積值的量級約 t² × chips,64k 時約 10¹⁰,double 沒問題。
- t 來自 `completed_iterations`,在 training state 裡，所以中斷再續跑的結果不變。
- 只支援 external sampling(和 C1 一樣)。

## 3. 為什麼應該有效 [推導 + 文獻]
LCFR 的理論收斂界和 CFR 同階，實務上(文獻的 poker 實驗)比 CFR 快很多，主要是因為早期的差策略被快速稀釋。我們的瓶頸正是很少被更新的節點被早期雜訊主導。[假設] 這在 draw 階段的效果最大。

## 4. 測試
- 預設 `uniform` 的固定 seed 指紋和改動前完全相同。
- `linear` 下，第 t 次迭代的 regret 和平均貢獻剛好是 `uniform` 的 t 倍：用同一份遊戲序列跑 2 次迭代，手算比對(第 1 次權重 1,所以第 1 次之後兩者完全相同;之後 regret 開始不同)。
- 中斷再續跑 = 一次跑完。

## 5. 什麼結果代表提案錯了
8k(和 day74 實驗同樣的牌局序列、fast sizing、seed 42),`simple + linear` 對 `simple + uniform`:
- 近均勻比例(實際打到)沒有比較低，**而且** SBR / 對打 / baselines 都沒有比較好 → 不採用。
- 任何一項顯著變差(> 2 SE)→ 不採用，先找原因。

## 6. 實作(day75)
- `CFRTrainer.iteration_weighting`:`"uniform"`(預設)或 `"linear"`;只能配 external sampling。`_iteration_weight()` 在 uniform 下回傳 1.0(乘 1.0 是精確的),所以預設路徑的固定 seed 指紋和改動前完全相同(md5_bucket_40 11,259 節點 `3adfdeef…`,md2_exact_15 1,604 節點 `d2a3031b…`)。
- `save_training_checkpoint --iteration-weighting`;只有非預設值才寫進 training state 的 config(舊 state 照樣續跑，換設定續跑會被拒絕)。
- C1:`solve_library add --iteration-weighting`,manifest `abstraction.iteration_weighting`(沒有這個欄位 = uniform)。checkpoint 格式(v3)不變。
- 實驗腳本 `scripts/train_weighting_variant.py`:和 day74 實驗同樣的牌局序列，所以 `simple + uniform` 就是 day74 的 simple checkpoint(有測試)。

測試(`tests/test_iteration_weighting.py`、`tests/test_training_run.py`):
- 明確指定 uniform = 原本的 trainer(指紋)。
- 實驗腳本的 `simple + uniform` 和 day74 實驗旁表逐位元相同。
- 第 1 次迭代後 linear = uniform;第 2 次迭代的增量剛好 2 倍(這組牌局沒有節點被更新兩次，所以這個測試只驗證權重，不驗證分歧後的軌跡)。
- 同一副牌重複 6 次(節點會被重訪):每次平均累積的權重都剛好等於 t。
- 30 次後 linear 和 uniform 確實不同。
- 中斷再續跑 = 一次跑完;換 iteration weighting 續跑會被拒絕。

## 7. 實驗結果
(跑完後填。)設定:fast sizing、`max_draw=5`、bucket、stack 20、seed 42,`simple + linear`,2k / 8k;基準 = day74 的 `avgmodes__simple__*`(同樣牌局序列)。
