# B2 提案：換牌(draw)策略品質分析

狀態：**分析與提案，未改 solver**(day56)。v1 數字已量;v2 數字待使用者執行(見第 5 節)。

標記:**[確認]** = 已用程式或實測驗證;**[推測]** = 推論。

工具:
- `scripts/inspect_draw_decisions.py`(新增，唯讀分析):把每個 draw 資訊狀態依 `DrawHandBucket` 分類，量策略放在明顯錯誤換牌上的機率，分「靜態」(所有已存狀態)和「reach-weighted」(self-play 實際打到的 draw 決策，和 `evaluate_checkpoint` 的 coverage 區段同一批牌、同一條動作路徑)。
- `tests/test_draw_mapping_properties.py`(新增)。

---

## 1. 換牌動作對應 [確認]

`tests/test_draw_mapping_properties.py`(9 個測試，全過):
- 每手牌的 32 個實際換牌動作 ↔ bucket 動作是一對一，來回轉換不變，`draw_count` 相同(400 手隨機牌)。
- 同一手牌換花色、打亂牌序後落在同一個 bucket,且每個 bucket 動作保留的點數與同花色張數完全相同(400 手)。
- bucket 標準順序依點數由小到大，`rank_classes` 對齊位置。
- 換 0 / 1 / 3 / 5 張後，進入 postdraw 的 key 裡 `action_history` 的 `draw_count` 與每位玩家的 `draw_count` 都正確。

結論：對應與 `draw_count` 編碼沒有發現錯誤。

## 2. 發現的問題

### 2.1 bucket 看不到順子聽牌結構 [確認]
`DrawHandBucket` 只存點數級別(2-3、4-5、6-7、8-9、T-J、Q-K-A)。例:
- 3-4-5-6-8 和 2-4-5-7-8 是同一個 bucket `(0,1,1,2,3)`。前者應丟 6(留 6-5-4-3 會被 2 或 7 湊成順子),後者丟 7 是錯的。
- 8-5-4-3-2 和 9-5-4-3-2 是同一個 bucket:pat 8 和 pat 9 的價值差很多。
- 無對子手牌中，丟一張後「剩下四張是不是順子聽牌」在同一 bucket 內結論不一致的情況:705 個(模式, 丟牌位置)中有 65 個(9.2%)。
- 實際影響：在 v1 的已訓練 made 8/9 狀態裡，有一個狀態 67% 機率放在「丟中間牌、留 8/9」。在 bucket 之下這可能是對的(打掉順子聽牌)也可能是錯的，策略無法區分。

### 2.2 `candidate` 換牌模式不符合 max_draw=5 的規則 [確認，程式碼]
`solver/discard_actions.candidate_discard_actions` 只產生換 0–3 張的動作(`max_draw >= 3` 之後沒有換 4、5 張)。v1 / v2 用的是 `full`,不受影響;但任何「縮減動作」的實驗若直接用 `candidate`,等於改了遊戲規則。

### 2.3 明顯錯誤換牌的頻率(v1,`max_draw=1`)[確認]

只算「可避免」的錯誤(同一狀態存在不犯該錯的合法動作)。兩種可靠的錯誤:
- **拆掉已成的 7 以下低牌**(無對子、無順子同花、全部 ≤ 7,卻換牌)。
- **保留對子**(換牌後仍保留兩張同點數)。

「留大丟小」因 2.1 的原因不可靠，只當參考，不計入。

| v1,20,000 局 self-play | 決策數 | 可避免錯誤機率 |
|---|---|---|
| 全部 draw 決策 | 30,086 | **15.1%** |
| 已訓練狀態 | 21,939 | 8.5% |
| 均勻(近似未訓練)狀態 | 6,581 | 35.0% |
| 查不到策略(均勻 fallback) | 1,566 | 24.4% |
| one pair,已訓練 | 8,167 | 22.8%(保留對子) |
| made 7 以下，已訓練 | 13 | 57.0%(拆掉成牌;狀態很少，靜態 28 個狀態也是 62%) |

讀法:
- 錯誤機率有一半以上來自未訓練或查不到的狀態(占 draw 決策的 27%)。主因是**訓練不足**,不是換牌邏輯錯。
- 已訓練狀態仍有 8.5% 錯誤，罕見狀態(made 7)尤其差 [推測：這些狀態的 strategy sum 很小，平均策略仍被早期均勻迭代主導]。

## 3. 提案

### P1(B2 可直接做，需核准):修正 `candidate` 模式的換牌張數
讓 `candidate_discard_actions` 在 `max_draw >= 4` 時也包含換 4、5 張的動作(例如各保留最佳 1–3 個)。
- 失敗模式:`max_draw=5` 下 candidate 模式少了合法動作。
- 測試：新增測試確認 `max_draw=5` 時每種張數都至少有一個動作;既有 checkpoint 不受影響(都用 `full`)。
- 推翻條件：無(規則問題)。

### P2(凍結介面，需走 version bump 與重訓):bucket 加入順子聽牌資訊
| 方案 | 無對子模式數 | 增加 |
|---|---|---|
| 目前 | 140 | — |
| R2:加 5 個旗標「丟位置 i 後剩下四張是否為順子聽牌」 | 187 | +34% |
| R3:R2 + 8 和 9 分開 | 243 | +74% |
| 完整點數 | 1,278 | ×9.1 |

建議 R2(必要時 R3)。只影響 predraw / draw 的 key(v2 中約占資訊集的 15%),[推測] 總資訊集增加約 5–11%。
- 失敗模式：同一 bucket 內正確換牌不同(2.1)。
- 驗證：同 seed、同迭代數訓練 R2 vs 現行，用 A2 benchmark 比 SBR 下界、draw 的 played 均勻比例與可避免錯誤。
- 推翻條件:R2 的 SBR 下界沒有顯著降低(< 2 SE),且 draw 可避免錯誤沒有下降。
- 這會讓所有 checkpoint 失效，要和 C1 的重訓排程一起。

### P3(ablation,不保證行為不變):移除明顯被支配的換牌動作
- 內容:draw 動作只保留「不保留對子」的動作(若存在),made 7 以下只保留 pat。[推測] 每個 draw 節點的平均動作數大幅下降，未訓練狀態的均勻機率不再浪費在明顯錯誤上，收斂應較快。
- 前提:P1 修好(或另寫縮減規則)。
- **評估時的注意事項**:目前 `evaluate_checkpoint` 的 SBR 用 checkpoint 自己的動作集合，縮減版 checkpoint 的 response 也被縮減，量到的是另一個遊戲的下界。ablation 需要「response 用完整 32 個動作、profile 在被移除的動作上機率為 0」的評估模式(A2 要加的功能)。
- 推翻條件：同迭代數下，縮減版在完整動作的 SBR 下界比 full 版高 2 SE 以上。

### 優先順序建議
1. 訓練不足是 draw 錯誤的主因 → 先等 A1 / C1 能跑更多迭代(A1 已把記憶體降到可跑 40k)。
2. P1(小、無風險)。
3. P2 和 C1 的下一次重訓一起做。
4. P3 需要 A2 先加「完整動作 response」評估，再做 ablation。

## 4. 不做的事
- 沒有改任何 solver 檔案或 checkpoint。
- 「留大丟小」不當錯誤指標(2.1)。
- snow(拿爛牌 pat 當詐唬)只列頻率，不當錯誤:適量 snow 是合理策略。

## 5. 待補:v2(max_draw=5)

```powershell
python -m scripts.inspect_draw_decisions checkpoints/production_v2_maxdraw5.chk.gz
```
約 5–10 分鐘、8 GB 記憶體，輸出 `experiments/eval/draw_decisions__production_v2_maxdraw5__s2027.json`。v2 是 B2 真正的對象(每個 draw 節點 32 個動作),數字出來後補進第 2.3 節並更新優先順序。
