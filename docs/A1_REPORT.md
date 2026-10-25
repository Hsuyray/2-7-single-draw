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
