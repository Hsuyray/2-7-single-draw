# D1 查詢 API(action 側)

狀態:**草案 v0.1,待你審核，尚未實作**(day67)。審核通過後，這份 JSON 格式就是凍結介面(CLAUDE.md 第 6 節),E1 依它開發。

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
| `R<金額>` | 加注 / 下注到該金額(本輪總投入)，例如 `R4.8`;All-in 也是 `R<全部籌碼>` |
| `D<n>` | 換 n 張，`D0` = stand pat |

例:`R4.8/C/D1/D2` = BTN 加到 4.8、BB 跟注、BB 換 1 張、BTN 換 2 張，輪到 BB 在 postdraw 行動。

金額比對用 `CHIP_EPSILON`,不用浮點相等(CLAUDE.md 修過的 bug 1)。

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
