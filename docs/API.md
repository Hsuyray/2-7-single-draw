# D1 查詢 API(action 側)

狀態:**草案 v0.2,尚未實作**(day67 草案;day68 依使用者回覆更新，見第 9 節)。審核通過後，這份 JSON 格式就是凍結介面(CLAUDE.md 第 6 節),E1 依它開發。

標記:**[確認]** = 程式或實測確認;**[推測]** = 推論;**[待決]** = 需要你決定。

Mock 回應(E1 可以直接用):`product/api/mock/*.json`。

---

## 0. 設計前提

1. **查詢不需要發牌**。產品的問題是「在這條公開行動路徑上，每種手牌怎麼打」。公開節點樹只取決於籌碼、盲注、下注尺寸和 `max_draw`,和牌無關(A1 的 `enumerate_public_tree.py` 已用這個性質)。所以 API 以**公開節點**為中心，每個節點一張「手牌 key → 動作頻率」的表。
2. **節點用行動路徑識別，不用浮點數**。`PublicNodeKey` 存的是原始浮點數(例如底池顯示成 `11.100000000000001`[確認]),不適合當 ID。金額只用來顯示，四捨五入到 0.1(`chip_increment`)。
3. **API 不暴露 seat,只用位置 `BTN` / `BB`**。訓練只用 `button_seat=0` [確認],而遊戲對座位對稱，所以伺服器固定把 BTN 對應到 seat 0、BB 對應到 seat 1 再查。這就在查詢層解決了「button 1 全部查不到」的問題，不需要重訓。
4. **讀 metadata 重建遊戲與下注尺寸**:用 A2 的 `setup_from_metadata`,不用 `checkpoint_browser.browser_from_checkpoint`(原因見第 7 節)。
5. **D1 只做 action 側**:每手牌 / 每格的動作頻率。range 依行動路徑的條件化與 EV 屬於 D2,本版的 range 匯總是「未條件化」的(第 4 節)。

## 1. 名詞

| 名詞 | 意思 |
|---|---|
| solution | 解庫中的一份解，ID 來自 `solutions/manifest.json`,例如 `hu_d5_full_bucket_s20` |
| checkpoint | 某份解在某個迭代數的策略，例如 `16000` |
| position | `BTN`(小盲，predraw 先行動、換牌後換、postdraw 後行動)或 `BB` |
| path | 從根節點開始的公開動作序列，見第 2 節 |
| hand key | solver 的抽象手牌:predraw / draw 用 `DrawHandBucket`,postdraw 用 `PostdrawStrengthBucket` |
| hand class | D3 的分格(`docs/HAND_TAXONOMY.md`,目前 v0) |

## 2. 路徑語法

動作 token 用 `/` 串接，根節點是空字串。

| token | 動作 |
|---|---|
| `F` | Fold |
| `X` | Check |
| `C` | Call |
| `R<百分比>` | 以底池百分比加注 / 下注，例如 `R50` = 50% Pot(day68 決定：決策依百分比看賠率與 MDF)。實際金額另在回應的 `raise_to` 欄位 |
| `RA` | All-in |
| `D<n>` | 換 n 張，`D0` = stand pat |

例:`R50/C/D1/D2` = BTN 下注 50% pot(加到 4.8)、BB 跟注、BB 換 1 張、BTN 換 2 張，輪到 BB 在 postdraw 行動。

[確認] 在 `full` 的完整公開樹(13,800 個決策節點)上，每個節點的百分比標籤和金額都沒有重複，所以 `R<百分比>` 能唯一決定動作。不同籌碼深度下同一個百分比對應不同金額，這正是用百分比的目的。

## 3. Endpoints(唯讀，JSON)

| Method | Path | 用途 |
|---|---|---|
| GET | `/v0/solutions` | 列出可用的解與 checkpoint |
| GET | `/v0/solutions/{solution}/{iterations}/node?path=...` | 節點資訊 + 合法動作 + 依手牌分格的頻率(Range Mode) |
| GET | `/v0/solutions/{solution}/{iterations}/hand?path=...&cards=7s5h4d3c2s` | 單一手牌的動作頻率(Hand Mode);draw 節點附上要丟哪幾張實際的牌 |

錯誤:路徑中有不合法的動作 → `404`,body 為 `{"error": "illegal_action", "at": "<出錯的 token>", "legal": [...]}`;手牌格式錯或和公開資訊衝突 → `400`。

## 4. 回應格式

### 4.1 `GET /v0/solutions`
見 `product/api/mock/solutions.json`。每份解:`id`、遊戲設定(籌碼、盲注、ante、`max_draw`)、抽象(下注尺寸、bucket)、可用的 checkpoint(迭代數、`sha256`、A2 評估摘要：判定、可剝削度下界、覆蓋率)。

### 4.2 `node`
見 `product/api/mock/node_root.json`、`node_draw_bb.json`。主要欄位:

```json
{
  "api_version": "0.1-draft",
  "taxonomy_version": "d3-v0",
  "solution": "hu_d5_full_bucket_s20",
  "iterations": 16000,
  "path": "R4.8/C",
  "history": [{"position": "BTN", "token": "R4.8", "label": "50% Pot"},
              {"position": "BB", "token": "C", "label": "Call"}],
  "phase": "draw",
  "actor": "BB",
  "pot": 11.1,
  "to_call": 0.0,
  "stacks": {"BTN": 15.2, "BB": 13.7},
  "actions": [{"token": "D0", "label": "Stand Pat", "kind": "draw", "draw_count": 0}],
  "range": {
    "weighting": "uniform_combos",
    "taxonomy": "predraw",
    "overall": {"D0": 0.08},
    "classes": [{"key": "pat_86", "label": "8-6 pat", "combos": 4080,
                 "frequencies": {"D0": 0.91}, "trained_share": 0.85}]
  },
  "coverage": {"trained_share": 0.62, "near_uniform_share": 0.31, "missing_share": 0.07}
}
```

- `actions[].token` 就是下一層路徑要用的 token;下注動作另有 `raise_to`、`pot_fraction`、`is_all_in`。
- `range.weighting = "uniform_combos"`:每格內每手牌依組合數平均，**沒有**依前面的行動條件化(那是 D2)。UI 要標示「未條件化 range」。
- `range.taxonomy`:predraw / draw 節點用 D3 的 predraw 分格(換牌前的牌),postdraw 節點用 postdraw 分格。
- 換牌節點的頻率依「換幾張」合併(`StrategyBrowser` 已這樣做);要看丟哪幾張，用 Hand Mode。
- `coverage` / `trained_share`:依組合數加權，策略是「已訓練」「接近均勻(和均勻的 total variation 距離 < 0.05 [待決])」「查不到」的比例。讓 UI 把不可靠的格子變灰。

### 4.3 `hand`
見 `product/api/mock/hand_draw_bb.json`。

```json
{
  "cards": ["8s", "6h", "4d", "3c", "Kd"],
  "hand_class": {"key": "draw1_8r", "label": "1-card draw to a rough 8 (8-6 / 8-7)"},
  "hand_key": "draw:(0,1,2,3,5)|mult:(1,1,1,1,1)|...",
  "status": "trained",
  "distance_from_uniform": 0.41,
  "frequencies": {"D0": 0.02, "D1": 0.93, "D2": 0.05},
  "discards": [{"draw_count": 1, "throw": ["Kd"], "probability": 0.90},
               {"draw_count": 1, "throw": ["8s"], "probability": 0.03}],
  "ev": null
}
```

- `discards`:把 bucket 的換牌動作(標準位置)透過 `actual_discard_action_for_bucket_hand` 對應到**這手牌實際的牌**[確認 B2 已驗證對應正確]。
- `hand_key`:抽象 key 的穩定字串，給除錯和快取用;UI 不必顯示。
- `ev`:D2 之前一律 `null`。
- `status`:`trained` / `near_uniform` / `missing`。`missing` 時 `frequencies` 為 `null`,不回傳假的均勻值。

## 5. 伺服器端的預先計算格式

v2 規模的 checkpoint 載入要約 8 GB [確認，A2],不能每個請求載入。建議每個 checkpoint 先建一個 **SQLite 檔**(標準函式庫，不加相依套件):

- `nodes(path, phase, actor, pot, to_call, stacks_json, actions_json)`:列舉全部公開節點(`full` 約 13,800 個 [確認，A1])。
- `strategies(path, hand_key, probabilities)`:每個節點、每個 hand key 的頻率(已依公開動作合併)。
- `class_frequencies(path, class_key, frequencies, combos, trained_share)`:預先算好每格的匯總，Range Mode 不必即時計算。
- 位置:`solutions/<id>/serving_<iterations>.sqlite`,不進 git(和 checkpoint 一樣)。

建置方式:`python -m product.api.build <solution> <iterations>`。
- 手牌分格到 hand key 的對應只算一次：列舉 2,598,960 手牌，記錄每格 → {hand key: 組合數}。`DrawHandBucket` 跟花色有關(同花聽牌),所以不能只看點數 [確認]。
- [推測] 建置在筆電上約 10–30 分鐘、峰值約 8 GB(載入 checkpoint);檔案大小約數十到數百 MB。實作時先量。

## 6. 實作計畫(審核後)

1. `product/api/build.py`:建 SQLite(第 5 節)。
2. `product/api/service.py`:純 Python 的查詢函式(輸入 path / cards,輸出第 4 節的 dict),不依賴 web framework,方便測試。
3. `product/api/app.py`:薄薄一層 HTTP。[待決] FastAPI(要加相依套件)或標準函式庫。
4. 測試:路徑解析、seat 對應(BTN / BB 查到的策略和直接用 seat 0 / 1 查 checkpoint 相同)、和 `StrategyIndex` 直接查詢的結果一致、mock 和實際輸出的 schema 一致。
5. 完成條件(WORKSTREAMS):用 v2(= C1 的 8k)從根節點一路查到 postdraw。

## 7. 發現的問題 [確認，程式碼]

**`checkpoint_browser.browser_from_checkpoint` 沒有傳下注尺寸設定**,只傳 `raise_sizes`。v1 / v2 / C1 的解都是 policy 模式(`raise_sizes = None`),瀏覽器因此用 `BetSizingPolicy()` 的預設值。預設值剛好等於 `full`(0.2 / 0.33 / 0.5 / 0.66 / 0.9 / 1.0 / 1.25),所以**目前的解碰巧沒事**;但 `fast` 的解會產生和訓練不同的合法動作，查詢會落空(違反 CFR 檢查清單「訓練和評估的合法動作相同」)。

`checkpoint_browser.py` 對 D1 是唯讀;建議修正(由擁有者處理):從 metadata 重建 `BetSizingPolicy`(A2 的 `setup_from_metadata` 已正確處理)並傳給 `StrategyBrowser`。D1 的實作不經過它，所以不受影響。

## 8. [待決] 需要你決定的事

1. **路徑語法**(第 2 節)OK 嗎?加注用金額(`R4.8`)還是用尺寸標籤(`R50`= 50% pot)?金額精確但不同深度不能共用;標籤直觀但 all-in 與重複尺寸要另外處理。
2. **HTTP 框架**:FastAPI(要加相依套件，有自動文件)或標準函式庫(零相依)。
3. **「接近均勻」的門檻**:total variation 距離 < 0.05?
4. **range 匯總的權重**:本版用未條件化的組合數(簡單、正確但不是實戰 range)。要等 D2 再一起出，還是先上這版並在 UI 標示?
5. **D3 的 6 個待決問題**:你說看過了，我先照 v0 的預設值;回應裡帶 `taxonomy_version`,之後改分格不會打壞 API。

## 9. day68 的決定與修改(使用者回覆)

| # | 問題 | 決定 | 對設計的影響 |
|---|---|---|---|
| 1 | 加注 token | **用底池百分比**(`R50`、`RA`) | 第 2 節已改;已確認全樹沒有重複標籤 |
| 2 | HTTP 框架 | 待決(差異已說明，見下) | — |
| 3 | 接近均勻的門檻 | **不用單一絕對值** | 見 9.1 |
| 4 | range 匯總 | **range 要依行動路徑條件化，雙方都要** | 見 9.2;這是原本 D2 的範圍 |

### 9.1 「接近均勻」的判定(取代固定的 0.05)
- 和均勻的 total variation 距離最大值是 1 − 1/n,依動作數 n 而不同(2 個動作最大 0.5,32 個動作最大約 0.97)。所以先**正規化**:`d / (1 − 1/n)`,0 = 完全均勻,1 = 完全確定。這樣 2 個動作和 32 個動作的節點可以用同一把尺。
- 有 C1 的訓練狀態檔時，再加上**統計依據**:每個資訊集的 `strategy_update_count`。更新次數太少的策略，就算看起來不均勻，也只是雜訊。門檻由實際資料決定：用 16k / 32k 的收斂量測(`inspect_state_convergence`)看「更新次數 vs 正規化距離」的關係後再定，不先寫死。
- 回應裡同時給 `distance_from_uniform`(正規化後)和 `strategy_updates`(有狀態檔時),讓 UI 自己決定怎麼顯示。

### 9.2 依路徑條件化的 range(雙方)
- 我方與對手的 range 都依「到這個節點為止各自的動作」做貝氏更新：每手牌的權重 = 起手組合數 × 這手牌在每個自己的決策點選了實際那個動作的機率。這就是均衡下「看到對手這樣打之後，他可能拿什麼牌」。
- 換牌時,range 依 solver 的換牌策略和精確的補牌機率轉移(`solver/hand_classes.draw_outcome_counts` 已實作;repo 也有 `draw_range_transition`)。
- 這原本是 D2 的範圍。因為 API 回應需要它，建議 D1 的實作分兩步:**先做 predraw 節點的條件化 range**(只需要每個 bucket 的權重，計算快、確定),再做跨換牌的轉移(和 D2 一起)。
- **「node lock」的兩種意思，要確認**:
  - (a) range 隨路徑鎖定 / 條件化 → 上面的做法，離線就能做。
  - (b) GTO Wizard 的 node locking:使用者手動改某個節點的策略，再**重新求解**其他節點 → 需要在查詢時跑 CFR,不符合「離線訓練一次、重複查詢」的產品前提，屬於之後的進階功能(E3)。

### 9.3 HTTP 框架的差異(問題 2)
| | FastAPI | 標準函式庫(`http.server`) |
|---|---|---|
| 相依套件 | 要加 `fastapi`、`uvicorn`(和它們的相依) | 不用 |
| 參數驗證、錯誤格式 | 自動(依型別宣告) | 自己寫 |
| API 文件 | 自動產生互動式文件頁(`/docs`) | 沒有，要手寫 |
| 同時處理多個請求 | 支援(async) | 基本的多執行緒;流量大時要換 |
| 適合 | 正式給 E1 / 多人使用 | 本機開發、測試 |

建議：查詢邏輯寫在不依賴框架的 `service.py`(第 6 節),HTTP 層很薄，兩種都能接;先用 FastAPI,因為 E1 要對著文件開發。這只影響第 6 節第 3 步，你確認後才加相依套件。
