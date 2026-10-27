# A1 報告:記憶體與規模(P0)

日期:2026-10-25。分支:`ws-a1-memory`(從 `main` @ `c41af03` 分出)。
沒有改 CFR 邏輯、`cfr_node.py`、`node_store.py`、key 或 checkpoint schema。新增的是量測工具。

標記:**[實測]** 這個 session 在容器裡跑出來的或你的檔案裡的數字;**[推算]** 從實測數字推出來的;**[推測]** 假設成分較多。
容器是 Python 3.11,你是 3.12。物件個數與「相同值」個數與版本無關;位元組數可能不同(見最後的指令,請在 3.12 重跑)。

---

## 0. 結論

1. **「40k 為什麼爆」的主要原因是狀態空間本身很大,加上每個節點太胖,不是洩漏,也不是浮點碎片化。**
2. **之前的 profiling 和 8k/40k 用的是不同的下注抽象。** 你的 1,000 次 profiling 用 `fast`(4 種尺寸),但 `production_v2_maxdraw5.chk.gz`(8k)的 metadata 顯示 `bet_pot_fractions = (0.2, 0.33, 0.5, 0.66, 0.9, 1.0, 1.25)`,也就是 `full`。兩者的公開節點樹差 6 倍(見 Q4)。
3. **每個節點約 4 KB,其中約 71% 是重複存放的相同物件**(同一個 `PublicAction`、`PublicPlayerState`、`DiscardAction` 被存了幾萬次)。把相同值共用一份,預估每節點降到約 1.15 KB。
4. **有證據支持的單一下一步**:在 `NodeStore.get_or_create` 建立新節點時做 interning(同值共用同一個物件)。這是行為不變的改動,但要動 `node_store.py`,需要你的核准。設計與驗證方式在第 5 節。

---

## 1. Q1:浮點碎片化?(結論:沒有)

- **假設**:同一個行動歷史對應到多個因浮點殘值而不同的 `pot`/`stack`,使得相同的狀態被存成多個節點。
- **方法(三個互相獨立)**:
  1. 對 `experiments/p0_small.chk.gz`(`fast`,1,000 次,114,110 個資訊集)跑 `inspect_node_composition.py`。
  2. 用新的 `scripts/enumerate_public_tree.py` 窮舉整棵公開節點樹,再把所有浮點數四捨五入到 6 位小數後重新計數。
  3. 直接掃描 checkpoint 裡所有浮點數。
- **證據 [實測]**:
  - 每個 phase 的「不同公開節點數」等於「不同歷史 key 數」:predraw 12/12,draw 133/133,postdraw 1,999/1,999。如果殘值把節點拆開,前者會大於後者。
  - 窮舉的公開節點數(`fast`,stack 20):12 / 133 / 2,016。四捨五入後仍是 12 / 133 / 2,016,**沒有任何節點被合併**。`full`:48 / 504 / 13,248,四捨五入後也完全相同。
  - checkpoint 裡有 70 個不同的浮點數,其中確實有殘值,例如 `3.5999999999999996` 與 `3.6`、`7.000000000000001` 與 `7.0`、`4.199999999999999` 與 `4.2`。但同一條路徑上的運算順序固定,殘值也固定,所以不會讓同一個狀態分成兩個節點。
  - 實際觀察到的 postdraw 公開節點數 1,999,沒有超過窮舉出的 2,016(我只比對了數量,沒有逐一比對內容)。
- **什麼會推翻這個結論**:換成別的 stack、`chip_increment` 或下注尺寸,四捨五入後節點數變少。腳本可以直接測任何設定(`--stack`、`--bet-sizing`)。
- **殘餘風險**:殘值存在,所以 key 對浮點很敏感。目前的設定沒有造成拆分,但這是巧合式的穩定,不是設計保證。把金額改存成整數(例如 `chips * 10`)會是結構上的修法,但那是凍結介面的改動,現在不建議做。

## 2. Q2:`copy.py` 的 42 MiB 為什麼留在記憶體裡?

- **假設**:`apply_solver_action` 每走一步都 `deepcopy(game)`,`PublicAction` 是 frozen dataclass,deepcopy 會重新建立每一個。`PublicNodeKey.from_game` 用 `tuple(game.action_history)` 直接引用這些剛複製出來的物件,於是儲存在節點表裡的 key 就把它們留住了。每個資訊集都有自己的一組歷史物件。
- **證據**:
  - **[實測] 物件普查**(`scripts/inspect_memory_model.py`,60 次迭代,13,209 個節點):`PublicAction` 有 **67,903 個不同的物件,但只有 50 種不同的值**;`PublicPlayerState` 26,418 個物件、260 種值;`PublicNodeKey` 13,209 個物件、1,709 種值。
  - **[推算] 區塊數吻合**:你的 tracemalloc 報告中,`copyreg.py:99` 有 220,352 個區塊,`copy.py` 有 442,541 個區塊,後者約為前者的兩倍(每個被複製的物件各一個物件加一個 dict)。按節點數把普查線性放大到 52,287 個節點,`PublicAction` 約 27 萬個,與 220,352 在同一數量級(成長不一定線性,所以只能當佐證,不是精確吻合)。
  - `public_state.py` 的 26.4 MiB 則對應 `PublicPlayerState`/`PublicNodeKey` 的建構(不是 deepcopy)。
- **結論**:`copy.py` 的記憶體不是洩漏,是被 key 合法引用的、**重複的** `PublicAction` 副本。
- **什麼會推翻**:做完 interning 之後,`copy.py` 的留存量沒有明顯下降。也可以用 `--tracemalloc-frames 12` 看呼叫堆疊直接確認,但會很慢(容器裡 30 次迭代超過 2 分鐘),所以我沒有跑。

## 3. Q3:`bucket_hand_codec.py:98–99` 建立了什麼?

- 第 98 行是 `DiscardAction(...)`,第 99 行是 `tuple(sorted(...))`(這個函式把原始棄牌動作轉成 bucket 標準順序的棄牌動作)。
- **數字完全吻合 [推算]**:300 次迭代時有 6,376 個 draw 節點,每個節點有 32 個棄牌動作(換 0 到 5 張的所有組合 = 2^5)。
  - 第 98 行:6,376 × 32 × 2 區塊(物件加 dict)= **408,064**,與實測的 408,064 完全相同。
  - 第 99 行:換 0 張的空 tuple 是共用的單例,所以是 6,376 × 31 = 197,656,實測 197,646。
- **這些物件存在哪**:`CFRNode.actions`(以及 `regret_sum`/`strategy_sum` 的 key)。**每個 draw 節點都存了自己的 32 個 `DiscardAction`,但全部加起來只有 32 種值。** 普查中 `action objects` 有 83,640 個物件、64 種值,占 11.1 MiB(約 22% 的記憶體)。
- 所以 draw 節點雖然只占節點數的 14%,32 個動作的重複存放讓它們占掉很大一塊。

## 4. Q4:飽和點與 40k 的外推

**狀態空間有確定的上限。** 資訊集 = (行動玩家, 公開節點, 自己的 bucket)。用 `enumerate_public_tree.py` 窮舉公開節點(stack 20、`max_draw=5`、button 0)[實測],再乘上每個 phase 的 bucket 數(predraw/draw 609、postdraw 128):

| 下注抽象 | 公開節點數 (predraw/draw/postdraw) | 資訊集上限 | 以 4.0 KB/節點估算 [推算] |
|---|---|---|---|
| `fast` | 12 / 133 / 2,016 | **346,353** | 1.3 GB |
| `full`(7 種比例) | 48 / 504 / 13,248 | **2,031,912** | 7.7 GB |

- 609 是在 checkpoint 裡觀察到的 draw bucket 數(predraw 與 draw 都剛好是 609),128 是 `POSTDRAW_BUCKET_COUNT`。這是上限,實際一定更少(有些 bucket 在某些節點不可能出現)。建議用 `scripts/inspect_draw_bucket_universe.py` 再確認 609。
- **進度**:`fast` 在 1,000 次時已到 114,110(33%);公開節點樹在 1,000 次時已幾乎全部走過(12/12、133/133、1,999/2,016),之後成長只來自「每個節點裡填入更多種 bucket」,postdraw 平均每個節點 47.4/128。
- **`full` 的 8k 檢查點** [實測]:`production_v2_maxdraw5.chk.gz` 有 **1,068,645** 個資訊集,已達上限的 53%。
- **40k 外推 [推測]**:把 `fast` 曲線的形狀(Weibull 型,指數約 0.83)套用到 `full` 的 8k 點,40k 約 **1.9M**(上限的 94%)。這個形狀是用 `fast` 的兩個點擬合的,尾端(罕見 bucket)可能比模型更慢,所以只能當粗略範圍:1.5M–2.0M。
- **記憶體 [推算]**:1.9M × 約 4 KB ≈ **7.6 GB**,還沒算 `full` 每節點動作更多造成的增加,也沒算存檔時的暫時峰值。8k 版本(1.07M)約 4.3 GB,在 16 GB 的機器上可以跑完,與它確實跑完吻合。
- **對 40k 失敗的解釋 [推測]**:你交接文件寫「超過 ~2 GB」,但如果那次也是 `full`,節點數會一路長到 100 萬以上,存檔(`strategy_index.strategies()` 再建一份,加上 pickle/gzip)又會疊上暫時峰值,足以讓 16 GB 的機器卡死。**使用者回報 40k 那次是 stack 20、bucket、full 下注(憑記憶,未驗證)**,與這個解釋一致。原本要請使用者確認的是這次實際的指令(`--bet-sizing`、`--stack`、`--abstraction`);`.tmp` 是中斷時留下的檔案,我沒有嘗試讀它的 metadata。
- **還缺的量測**:`full` 在 2k/4k 的節點數,可以驗證 Weibull 擬合。指令見第 6 節。

---

## 5. 記憶體模型與候選優化

### 每節點記憶體 [實測,Python 3.11,60 次迭代,`fast`]

| 結構 | 引用數 | 不同物件 | 不同值 | B/物件 | 總計 MiB | 共用後可省 MiB |
|---|---:|---:|---:|---:|---:|---:|
| CFRNode | 13,209 | 13,209 | 13,209 | 184 | 2.32 | 0 |
| regret_sum dict | 13,209 | 13,209 | 13,209 | 331 | 4.17 | 0 |
| strategy_sum dict | 13,209 | 13,209 | 13,209 | 331 | 4.17 | 0 |
| actions tuple | 13,209 | 13,209 | 31 | 91 | 1.14 | 1.14 |
| action objects | 83,640 | 83,640 | 64 | 139 | 11.12 | 11.11 |
| InformationState | 13,209 | 13,209 | 13,209 | 152 | 1.91 | 0 |
| PublicNodeKey | 13,209 | 13,209 | 1,709 | 192 | 2.42 | 2.11 |
| players tuple | 13,209 | 13,209 | 915 | 56 | 0.71 | 0.66 |
| PublicPlayerState | 26,418 | 26,418 | 260 | 184 | 4.64 | 4.59 |
| action_history tuple | 13,209 | 13,155 | 1,709 | 81 | 1.02 | 0.89 |
| PublicAction | 67,903 | 67,903 | 50 | 226 | 14.64 | 14.63 |
| own_hand_key | 13,209 | 4,189 | 227 | 173 | 0.69 | 0.65 |
| float values | 167,280 | 61,115 | 4,706 | 24 | 1.40 | 1.29(不可共用) |
| **合計** | | | | | **50.3** | |

- 每節點 **3,997 B**,與你的實測 RSS 斜率(約 3.9 KB/節點)很接近。位元組數是 `sys.getsizeof` 加上實例 dict,不含配置器開銷;兩個版本的接近可能有巧合成分。
- 可共用的部分(扣掉浮點數):35.8 MiB = **71%**,共用後約 **1,150 B/節點**。
- 共用之後剩下的主要是:兩個 dict(662 B)、`CFRNode`(184 B)、`InformationState`(152 B)、浮點數(約 110 B)。
- **注意**:這是 `fast` 的普查。`full` 每個節點的動作更多,dict 更大,要用同一支腳本實測(第 6 節)。

### 候選優化(依預期效果排序,**全部尚未實作**)

| # | 做法 | 預期節省 | 行為是否不變 | 風險 |
|---|---|---|---|---|
| 1 | **Interning**:`NodeStore.get_or_create` 建立新節點時,把 key 內的 `PublicAction`/`PublicPlayerState`/`PublicNodeKey`/`own_hand_key` 與 `node.actions` 換成同值的共用物件 | 約 70%(4.0 → 1.15 KB/節點);`full` 上限 7.7 GB → 約 2.2 GB | 是(相等性與雜湊不變) | 低;只在新建節點時多一次查表,查詢路徑不變 |
| 2 | `CFRNode` 的 `regret_sum`/`strategy_sum` 改用 `array('d')` 或 list(依 actions 順序) | 再省約 0.4–0.5 KB/節點 [推測] | 數值應相同,但 API(dict)被許多測試與 `strategy_browser` 使用 | 中;介面變更面積大,先做 #1 |
| 3 | `CFRNode` 加 `__slots__` | 約 50–100 B/節點 [推測] | 是 | 低,但效益小 |
| 4 | 存檔時串流寫出,避免再建一份完整 `strategies()` | 降低存檔峰值 | 檔案內容相同 | 要先量到存檔峰值才知道值不值得(見第 6 節新增的 `peak_rss_bytes`) |
| 5 | 把金額改成整數 | 無記憶體效益,是穩健性 | 否(key 改變) | 高,凍結介面,不建議 |

### 提案:#1 Interning(需要你核准才會實作)

- **失敗模式**:相同值的物件被存了幾萬份,占約 71% 的節點記憶體。
- **為什麼會有效**:`dict` 的鍵比對只看相等性與雜湊;換成同值的共用物件,查詢結果完全相同。已建立的節點不受影響。
- **驗證方式**:
  1. 固定 seed 42、`max_draw=5`、`fast`、100 次迭代,改動前後比較:節點數、`nodes.keys()` 的順序與內容、每個節點的 `regret_sum`/`strategy_sum`,全部必須完全相同(沿用 `tests/test_memory_guard.py` 的比較方式)。
  2. 再跑一次 `scripts/inspect_memory_model.py`:`PublicAction` 的「不同物件」數必須降到約等於「不同值」(約 50),每節點位元組降到約 1.2 KB 以下。
  3. 1,000 次 profiling 的 RSS 與 `p0_small_rss.csv` 比較。
- **什麼結果會推翻它**:任何策略差異;或每節點位元組降幅小於 40%。
- **範圍**:只改 `solver/node_store.py`(加一個 intern 表),另外新增測試。`cfr_trainer.py`、`public_state.py`、`information_state.py` 不動。

---

## 6. 請你在 Windows / Python 3.12 上跑的指令(依序)

```powershell
git fetch origin
git checkout ws-a1-memory     # 推上去之後;或把這個 session 的變更帶過去

python -m pytest tests -q

# (a) 3.12 上的物件普查:fast 與 full 各一次(約 1 分鐘與 3 分鐘,未實測)
python -m scripts.inspect_memory_model --iterations 100 --bet-sizing fast
python -m scripts.inspect_memory_model --iterations 100 --bet-sizing full

# (b) 用你實際的設定確認上限與碎片化(5 秒 / 40 秒)
python -m scripts.enumerate_public_tree --bet-sizing fast
python -m scripts.enumerate_public_tree --bet-sizing full
python -m scripts.inspect_draw_bucket_universe   # 確認 609

# (c) full 的成長曲線與存檔峰值(約 20–30 分鐘,未實測;--no-tracemalloc 比較快)
python -m scripts.profile_memory --iterations 2000 --sample-every 100 --bet-sizing full --no-tracemalloc --checkpoint-output experiments\a1_full_2k.chk.gz --csv experiments\memory_profile\a1_full_2k.csv
```

- (c) 的 CSV 新增 `peak_rss_bytes` 欄(進程的高水位),在 `after_checkpoint_save` 那列會包含存檔時的暫時峰值。報告中的 `process peak RSS` 也是同一個數字。
- 有問題的徵兆:`enumerate_public_tree` 四捨五入後的節點數比原本少(代表有碎片化);普查的「不同物件」數明顯不大於「不同值」(代表我的重複物件結論不成立)。
- 請把 (a)(b)(c) 的輸出和 40k 那次的指令給我,我再更新第 4 節的外推。

---

## 7. 沒有驗證的部分

- 位元組數是 Python 3.11 的 `getsizeof`,不是 3.12,也不是進程 RSS。
- `full` 設定下的每節點位元組數、成長曲線都還沒量到;40k 的節點數與記憶體是模型外推。
- 609 這個 draw bucket 數是從 checkpoint 觀察到的,不是從 bucket 全集窮舉出來的(你的 `inspect_draw_bucket_universe.py` 可以確認)。
- 窮舉公開節點樹時,draw 節點每種張數只取了一個代表棄牌,假設公開 key 只取決於張數。`fast` 的觀察值(133 個 draw 節點、1,999 個 postdraw 節點)與窮舉值一致,支持這個假設。
- 沒有直接用 tracemalloc 堆疊證明 `copy.py` 的來源(第 2 節是由物件普查與區塊數推出來的)。
- 存檔的暫時峰值還沒量到(只有存檔後 RSS +0.085 GB,在 114k 節點時)。

---

## 8. Windows / Python 3.12.9 實測(day37,使用者提供)

### 8.1 物件普查(100 次迭代,seed 42,stack 20)

| 下注抽象 | 節點數 | 耗時 | B/節點 | 可共用比例 | 共用後 B/節點 |
|---|---:|---:|---:|---:|---:|
| `fast` | 21,487 | 60.2 s | 3,881 | 74% | 1,026 |
| `full` | 51,514 | 130.3 s | 3,788 | 73% | 1,024 |

- 與 3.11 的 3,997 B/節點(`fast`)很接近,結論不依賴 Python 版本。
- `full` 在 100 次迭代時節點數是 `fast` 的 2.4 倍,每次迭代慢約 2.2 倍(1.3 s vs 0.6 s)。
- `full` 的最大幾項(MiB,共 186.1):`PublicAction` 59.9(51.5 萬個引用中 286,839 個物件,只有 **174 種值**)、`action objects` 35.8(283,460 個物件,**125 種值**)、`PublicPlayerState` 17.3(1,450 種值)、兩個 dict 合計 31.0(無法共用)。
- 三個互相獨立的檢查(`fast`/`full` 的碎片化測試)都再次重現:四捨五入後節點數不變。

### 8.2 `full` 跑 2,000 次(含存檔)

| 指標 | 數值 |
|---|---|
| 節點數 | 562,244(draw 53,181、postdraw 495,860、predraw 13,203) |
| 耗時 | 訓練 2,534 s(約 1.27 s/次,與前 100 次一致) |
| 存檔後 RSS | 2.447 GB(約 4.7 KB/節點,含存檔殘留) |
| **進程峰值(含存檔)** | **3.666 GB** |
| 存檔造成的暫時增量 | 至少 1.22 GB(約 2.3 KB/節點);「至少」是因為存檔前的 RSS 不會比存檔後的高 |
| lru_cache | 全部很小(`_score_to_bucket` 1 筆,其他 0 筆),**再次排除快取洩漏** |

### 8.3 `full` 的成長與上限

| 迭代 | 節點數 | 占上限 2,031,912 | 來源 |
|---:|---:|---:|---|
| 100 | 51,514 | 2.5% | 普查 |
| 2,000 | 562,244 | 27.7% | 2k 實測 |
| 8,000 | 1,068,645 | 52.6% | `production_v2_maxdraw5.chk.gz` |

- 以 `-ln(1 - 占比)` 看成長指數:100→2,000 約 0.85,2,000→8,000 約 0.60,**越來越慢**(罕見的 bucket 組合很晚才出現)。所以先前用 `fast` 擬合出的 1.9M 太樂觀。
- **40k 的節點數 [推測]:約 1.5M–1.75M**(上限的 74%–86%),假設指數繼續降到 0.4–0.6。

### 8.4 記憶體預測 [推算]

用 4.2–4.7 KB/節點(穩態)與「存檔暫時增量至少 2.3 KB/節點」:

| 情境 | 節點數 | 訓練時 RSS | 存檔時峰值 |
|---|---:|---:|---:|
| 8k(已成功跑完) | 1.07M | 4.2–4.7 GiB | 至少 6.5–7 GiB |
| **40k(估計)** | 1.5–1.75M | 6–7.7 GiB | **至少約 10–11 GiB** |
| 上限 | 2.03M | 8–9 GiB | 至少 12.5–13.5 GiB |

- 在 16 GB 的機器上,加上 Windows、瀏覽器、OneDrive 等,**存檔時的峰值接近或超過實體記憶體**,會大量換頁而卡死。這與「40k 時整台機器卡死」且 `.tmp` 檔(52.9 MB)停在寫到一半相吻合。
- 8k 版本剛好可以跑完(峰值約 7 GiB)。
- 因此問題有兩個: (1) 穩態每節點太胖(第 5 節);(2) 存檔時還要再疊上至少 50% 的暫時記憶體。

### 8.5 Interning 的預期效果 [推算]

- 穩態:共用後 1.03 KB/節點(帳面)× RSS/帳面比約 1.1–1.24 ≈ 1.1–1.3 KB/節點。40k(1.5–1.75M 節點)約 **1.6–2.2 GiB**,上限(2.03M)約 2.2–2.5 GiB。
- 存檔峰值 [推測]:pickle 的 memo 以物件 id 記錄每個物件;共用之後需要記錄的不同物件大幅減少,所以暫時增量也應該跟著降。這一點沒有實測,需要在做完 interning 後用同一個指令(`--iterations 2000 --bet-sizing full`,看 `process peak RSS`)比較。
- 做完後的驗收標準: (1) 固定 seed 的節點、regret、strategy sum 與改動前完全相同;(2) 2k 次的存檔後 RSS 從 2.447 GB 降到 1.0 GB 以下;(3) 進程峰值從 3.666 GB 降到 2 GB 以下。若 (2) 沒有降幅超過 40%,提案被推翻。

### 8.6 其他觀察

- `full` 每次迭代約 1.27 s,**8k 約 2.8 小時,40k 約 14 小時**,而且是單執行緒。這影響 P1(高迭代正式 checkpoint)的規劃,也是多核心(C2)的動機。

### 8.7 修正:存檔暫時增量的精確值(來自 `a1_full_2k.csv`)

CSV 有存檔前的 RSS,所以不必再用「至少」:

| 時間點 | RSS | 每節點 |
|---|---:|---:|
| 第 2,000 次、存檔前 | 2.097 GiB | 3.9 KB |
| 存檔期間的進程峰值 | 3.666 GiB | 6.7 KB |
| 存檔後 | 2.447 GiB | 4.7 KB |

- **存檔暫時增量 = 3.666 - 2.097 = 1.57 GiB(約 3.0 KB/節點),是穩態的 75%。**(day41 更正:原寫 2.8 KB,是單位換算錯誤) 存檔後還有 0.35 GiB 沒有還給系統。
- 先前 8.4 節用「至少 2.3 KB/節點」估的峰值偏低。以 4.0 KB 穩態 + 3.0 KB 暫時增量重算:40k(1.5–1.75M 節點)的峰值約 **9.7–11.3 GiB**,上限(2.03M)約 **13.2 GiB**。結論不變,只是更接近 16 GB 的極限。

---

## 9. Interning 的實作與驗證(day38)

### 9.1 改了什麼

- **只改 `solver/node_store.py`**:`NodeStore` 新增欄位 `intern: bool = True`。建立**新**節點時,key 內的 `PublicPlayerState`、`PublicAction`、`PublicNodeKey`、手牌 key,以及 `actions` 的元素與 tuple,都換成同值共用的那一份(以 `dataclasses.replace` 重建 key,其餘欄位原樣保留)。已存在的節點、查詢路徑、`remove`、`average_strategies` 不變;`clear()` 同時清空共用表。
- `intern=False` 會原樣儲存傳入的物件,等同改動前的行為。
- 沒動 `cfr_trainer.py`、`cfr_node.py`、`public_state.py`、`information_state.py`、key 格式與 checkpoint schema。
- 新增 `scripts/fingerprint_node_store.py`(固定 seed 的節點表指紋)與 `tests/test_node_store_interning.py`(10 個測試)。

### 9.2 驗證結果(容器,Python 3.11)

1. **改動前後指紋相同。** 改動前(`main` 的程式碼)與改動後各跑一次 `md5_bucket_40`(8,916 個節點)與 `md2_exact_15`(1,979 個節點);指紋(對每個資訊集的 repr、動作、精確的 regret/strategy sum(`float.hex`)、更新次數做 sha256)**完全相同**。
2. **新測試**:相同 seed 下 `intern=True` 與 `intern=False` 訓練出的節點順序、每個節點的 regret/strategy sum、平均策略完全相等(bucket 與 exact 各一組);訓練後 `intern=True` 的 `PublicAction` 與動作物件「不同物件數 = 不同值數」,`intern=False` 則有大量重複。
3. **全部測試**:819 個通過(含 checkpoint 存讀測試)。
4. **效果(60 次迭代,`fast`,13,209 個節點,相同的節點數)**:

| | 改動前 | 改動後 |
|---|---:|---:|
| 帳面位元組 | 50.3 MiB | **14.6 MiB** |
| 每節點 | 3,997 B | **1,161 B**(-71%) |
| `PublicAction` 物件數 | 67,903 | 50 |
| `PublicPlayerState` 物件數 | 26,418 | 260 |
| 動作物件數 | 83,640 | 64 |

   與 8.5 的預測(約 1.03 KB)接近;多出來的是 `players tuple` 沒有完全共用(1,709 個物件對 915 種值,因為共用的是 `PublicNodeKey` 內的 tuple,而相同內容的 tuple 來自不同的 key)。這部分只有約 0.04 MiB,不影響結論。
5. **速度**:指紋腳本改動前 45.6 s、改動後 46.4 s(同機器,差異在雜訊內)。容器的其他計時受機器負載影響,不能拿來比較;請以第 9.3 的 2,000 次實測為準。

### 9.3 請你在 Windows / Python 3.12 上驗證

```powershell
git fetch origin
git checkout ws-a1-memory
python -m pytest tests -q

# (1) 指紋:改動前後(只暫時換回 main 的 node_store.py)
python -m scripts.fingerprint_node_store > after.json
git checkout main -- solver/node_store.py
python -m scripts.fingerprint_node_store > before.json
git checkout ws-a1-memory -- solver/node_store.py
git status --short          # 只應有 after.json、before.json 兩個未追蹤檔,沒有 M 開頭的行
# 注意:PowerShell 裡的 fc 是 Format-Custom 的別名,不是檔案比較。請用下面任一個:
Compare-Object (Get-Content before.json) (Get-Content after.json)   # 沒有任何輸出 = 相同
git diff --no-index --stat before.json after.json                    # 沒有任何輸出 = 相同

# (2) 同一個 2,000 次 full(約 40 分鐘),和第 8.2 節比較
python -m scripts.profile_memory --iterations 2000 --sample-every 100 --bet-sizing full --no-tracemalloc --checkpoint-output experiments\a1_full_2k_interned.chk.gz --csv experiments\memory_profile\a1_full_2k_interned.csv
```

驗收標準(第 8.5 節):
- (1) 比較指令沒有任何輸出(兩個 JSON 相同);
- (2) 節點數仍是 **562,244**(相同 seed,應完全相同);存檔後 RSS 從 2.447 GB 降到 1.0 GB 以下;`process peak RSS` 從 3.666 GB 降到 2 GB 以下。存檔後 RSS 降幅不到 40% 就算提案被推翻。

(1) 的指紋只能在同一個 Python 版本內比較,所以請在你的 3.12 上兩次都跑,不要和我貼的容器數字比。

---

## 10. Interning 實測結果(day41,Windows / Python 3.12,使用者提供)

同一個指令:`full`、stack 20、bucket、seed 42、2,000 次、存檔。改動前的數字來自 `experiments/memory_profile/a1_full_2k.csv`。

| 指標 | 改動前 | interning 後 | 變化 | 驗收標準 |
|---|---:|---:|---:|---|
| 節點數 | 562,244 | **562,244** | 相同 | 必須相同:**通過** |
| 各 phase 節點數 | 53,181 / 495,860 / 13,203 | 53,181 / 495,860 / 13,203 | 相同 | |
| 每 100 次的節點數(全部 20 個取樣點) | | 與改動前逐點相同 | 相同 | |
| 存檔前 RSS | 2.097 GiB(4,005 B/節點) | **0.618 GiB(1,181 B/節點)** | **-70.5%** | |
| 存檔後 RSS | 2.447 GiB | **0.667 GiB** | **-72.7%** | < 1.0 GB:**通過** |
| 存檔期間進程峰值 | 3.666 GiB | **1.381 GiB** | **-62.3%** | < 2 GB:**通過** |
| 存檔暫時增量 | 1.57 GiB(3.0 KB/節點) | 0.76 GiB(1.5 KB/節點) | -51% | |
| 訓練速度(第 1,000 到 2,000 次) | 1,245 s | 1,264 s | +1.5% | 雜訊範圍 |

- **提案成立**:三個驗收條件都通過,節點數逐點相同。容器內的帳面預測是 1,161 B/節點,實測 1,181 B/節點。
- **存檔峰值也降了一半**(推測的 pickle memo 機制與結果一致,但沒有直接量 memo)。
- **計時異常(不是 interning 造成的)**:總時間 13,587 s,改動前 2,534 s。但第 1,000–2,000 次兩者幾乎一樣(1,264 s vs 1,245 s);差距集中在第 500–900 次(多出約 1 萬秒,例如 800→900 用了 5,414 s),像是電腦睡眠或被其他程式占用。前 500 次也慢了 1.9 倍(1,258 s vs 663 s),原因不明。若要確認速度,請在不使用電腦、接上電源的情況下重跑。
- **指紋比較(day42,Windows / Python 3.12)**:改動前(`main` 的 `node_store.py`)與改動後的 `scripts/fingerprint_node_store.py` 輸出,`Compare-Object` 與 `git diff --no-index` 都沒有任何差異。**interning 在 3.12 上也被證明是行為不變的。**

### 10.1 interning 之後的記憶體預測 [推算]

用 1,181 B/節點(穩態)+ 1,456 B/節點(存檔暫時增量):

| 情境 | 節點數 | 訓練時 RSS | 存檔時峰值 | 改動前的峰值 |
|---|---:|---:|---:|---:|
| 8k | 1.07M | 1.2 GiB | 2.6 GiB | 約 7 GiB |
| 40k(估計) | 1.5–1.75M | 1.65–1.9 GiB | **3.7–4.3 GiB** | 9.7–11.3 GiB |
| 上限 | 2.03M | 2.2 GiB | 5.0 GiB | 13.2 GiB |

**結論:`full` 的 40k 在 16 GB 的機器上已經跑得動。** 要注意三件事:

1. `save_training_checkpoint.py` 預設每 500 次存一次(`--checkpoint-every-batches 1`),40k 會存 80 次,每次都會碰到存檔峰值、也要花時間。長時間訓練建議 `--checkpoint-every-batches 10` 左右。
2. RSS guard(預設 3 GB)只在訓練中檢查,存檔時不檢查。40k 存檔峰值約 4 GiB,所以 guard 本身不會擋住存檔;若要更保險,可以把 `--max-rss-gb` 設成 6。
3. `full` 每次約 1.25 s,40k 約 14 小時(單執行緒)。
