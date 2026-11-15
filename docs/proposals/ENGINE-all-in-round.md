# 提案：面對 all-in 的玩家沒有機會行動(遊戲引擎 bug)

狀態:**已修正(day70,使用者核准)**。day69 在 D1 實作時發現。結果見第 7 節。day70 前的所有 checkpoint 都是舊規則。

標記:**[確認]** = 程式或實測確認;**[推測]** = 推論。

## 1. 現象 [確認]
單挑、籌碼 20、盲注 1 / 2、ante 1.5,button = seat 0。BTN 在根節點 all-in(加到 20):
- 遊戲**直接進入換牌**,輪到 BB 換牌。BB 本輪只投入 2、手上還有 16.5,沒有 all-in,**從頭到尾沒有機會跟注或棄牌**。
- 換牌後也沒有下注，直接攤牌。輸贏只有 BB 原本投入的部分:3 個 seed 的結果是 BTN +3.5 / +3.5 / −2.0。BTN 多下的 16.5 沒有被跟注，退還給 BTN。
- 對照：加注到 8.9(不是 all-in)時,BB 正常輪到行動。

重現:原本是 `tests/test_known_bugs.py` 的 strict xfail;day70 起改為 `tests/test_regression_fixed_bugs.py` 的回歸測試。

## 2. 根本原因 [確認，程式碼]
`solver/game_state.py`,`BettingState._is_betting_round_complete`:

```python
eligible_players = [
    player for player in self.players
    if not player.has_folded and not player.is_all_in
]

if len(eligible_players) <= 1:
    return True        # ← 沒檢查剩下的那位是否已跟上下注
```

BTN all-in 之後,「沒棄牌、沒 all-in」的只剩 BB,函式直接回傳「這一輪結束」。多人桌也一樣:其他人都 all-in 時，最後一位還欠籌碼的玩家也不會被問。

## 3. 影響
- **所有訓練過的 checkpoint**(v1、v2、C1 的 8k / 16k)都是在這個錯誤規則下訓練的。all-in 在 solver 裡等於「強迫對手用很小的籌碼攤牌」:對手不能棄牌，也不能被迫付出全下的籌碼。
- 公開樹裡有 5,893 個 All-in 動作 [確認，day68 的全樹統計]。修正後,all-in 之後會多出「對手跟注 / 棄牌」的節點，樹會變大。
- [推測] 對策略的影響很大：作為下注選項,all-in 的風險被嚴重低估;對手面對 all-in 時的跟注 / 棄牌策略完全不存在。A2 的評估、B2 的換牌分析，凡是牽涉 all-in 的路線都受影響。
- **C1 的 32k 訓練應先暫停**(`docs/PENDING_RUNS.md` 已標註):在錯誤的遊戲上多訓練沒有意義。

## 4. 修正方案
```python
def _is_betting_round_complete(self) -> bool:
    eligible_players = [
        player for player in self.players
        if not player.has_folded and not player.is_all_in
    ]

    if not eligible_players:
        return True

    if len(eligible_players) == 1:
        # Everyone else is all-in or folded: the round is over
        # once the remaining player has matched the bet.
        player = eligible_players[0]
        return (
            player.committed_this_round
            >= self.current_bet - CHIP_EPSILON
        )

    ...  # 其餘不變
```

還要一起確認(實作時):
- 只剩一位可以行動、而其他人都 all-in 時，這位玩家**不應該能加注**(沒有人能跟)。要檢查 `legal_actions` 在這種情況下是否只給棄牌 / 跟注。
- 跟注 all-in 時，如果自己的籌碼不夠(all-in for less),退還多出的部分要和現有的分彩池邏輯一致(`_award_pots` 已有 side pot,實作時用測試確認)。

## 5. 驗證方式
1. `tests/test_known_bugs.py` 會從 xfail 變成通過 → 移除 xfail 標記，改成回歸測試(並加進 `tests/test_regression_fixed_bugs.py` 的說明)。
2. 新增測試:BB 跟注 all-in 後雙方 all-in → 換牌後沒有下注、直接攤牌，輸贏是完整的有效籌碼;BB 棄牌 → BTN 贏下底池。三人桌：兩人 all-in、第三人欠籌碼時要被問。
3. 全部既有測試要通過。會改變行為的只有「面對 all-in」的情況;行為不變的部分用固定 seed 的訓練指紋比對(沒有 all-in 的設定，例如 `--bet-sizing none`,修正前後的節點表應完全相同)。
4. 用 `scripts.enumerate_public_tree` 重算公開節點數，記錄增加多少。

**什麼結果代表修正錯了**:沒有 all-in 的設定，修正前後的訓練指紋不同(代表動到了不該動的地方);或零和、籌碼守恆的檢查失敗。

## 6. 修正之後
- 升級說明:CLAUDE.md 的「已修正 bug」加一項;所有 checkpoint 標為「舊規則」。
- C1:用修正後的引擎從 0 重訓 `hu_d5_full_bucket_s20`(8k 起)。舊的 8k / 16k 保留作對照，不刪。
- A2:重跑 v2 / 新 8k 的評估。

## 7. 實作與驗證結果(day70)[確認]

### 7.1 改了什麼
- `solver/game_state.py` `_is_betting_round_complete`:只剩一位可以行動(其他人棄牌或 all-in)時，要等這位**跟上下注**才結束本輪(第 4 節的方案)。
- `solver/game_state.py` `legal_actions`:**至少還有一位對手可以回應**(沒棄牌、沒 all-in)才能加注。否則面對 all-in 時只有棄牌 / 跟注。
- `solver/legal_actions.py` `_raise_is_legal`:先問引擎允不允許加注(`ActionType.RAISE in state.legal_actions()`),兩邊用同一個判斷。
- 跟注 all-in 但籌碼不夠(all-in for less)時，多出來沒被跟的部分由現有的 `build_pots` 退還，不用改程式;測試確認。

### 7.2 測試(`tests/test_regression_fixed_bugs.py` 第 3 節，7 個)
- BTN all-in → BB 只能棄牌 / 跟注(引擎和 `legal_actions` 兩邊都檢查)。
- BB 跟注 → 雙方換牌後直接攤牌，輸贏是完整的有效籌碼:BTN 贏 +20 或輸 −18.5(BB 的 1.5 ante 是 dead money;BTN 多出的 1.5 沒被跟，退還),平手 +0.75;seed 1–3。
- BB 棄牌 → BTN 贏 +3.5。
- 籌碼不等：大籌碼面對短籌碼 all-in 不能再加注;短籌碼跟注 all-in for less 時最多輸自己的 20。
- 三人桌:BTN all-in、SB 跟注 all-in,BB 還欠籌碼 → 要被問。
- 一般加注之後仍然可以再加注(沒有誤傷)。
- 全部測試:**928 passed**(day69 是 921 passed + 1 xfailed)。

### 7.3 固定 seed 的訓練指紋(`scripts/fingerprint_node_store.fingerprint_trainer`,seed 42,籌碼 20)

| 設定 | 修正前 | 修正後 | 相同? |
|---|---|---|---|
| 不能加注(`raise_sizes=()`),`max_draw=5`,bucket,60 次 | 2,972 節點 / `285f49dfa430a9e2` | 同左 | **完全相同** |
| 不能加注,`max_draw=2`,exact,30 次 | 1,165 / `7387557d3e4ffcf8` | 同左 | **完全相同** |
| 只能加注到 4(到不了 all-in),`max_draw=5`,bucket,60 次 | 8,370 / `b71f40c947fccdd8` | 同左 | **完全相同** |
| `fast`(含 all-in),`max_draw=5`,bucket,40 次 | 8,916 / `608d5430545dd459` | 11,259 / `3adfdeef3c62e715` | 不同(預期) |

結論：沒有 all-in 的設定，節點表與策略逐位相同;只有會出現 all-in 的設定改變。

### 7.4 公開樹(`python -m scripts.enumerate_public_tree --max-draw 5`,籌碼 20)

| sizing | 公開節點 修正前 → 後 | info set 上限 修正前 → 後 | 記憶體上限(× 3,900 B) |
|---|---|---|---|
| none | 不變 | 不變 | 不變 |
| fast | 2,161 → 3,321 | 346,353 → 498,681(+44%) | 1.26 → 1.81 GB |
| full | 13,800 → 19,405 | 2,031,912 → 2,761,377(+36%) | 7.38 → 10.03 GB |

上限是「每個公開節點 × 所有手牌 key」,實際訓練到的節點少很多(舊規則 16k 是 1,332,829 個)。

### 7.5 訓練成本(`full`,`max_draw=5`,bucket,seed 42,300 次;兩個同時跑在雲端)
- 節點:142,215 → 170,391(+20%)。每次迭代約 1.07 → 1.09 秒(差異在雜訊內)。
- [推測] 16k 峰值記憶體從 3.84 GB 增加到約 4.6–5.2 GB(依節點 +20–36% 推算);32k 約 6–7 GB。`solve_library train` 的 RSS 上限預設 10 GB,16 GB 的筆電夠用。

### 7.6 受影響的測試
`tests/test_sbr_power.py::test_full_leak_is_found_by_reference_and_grouped_sbr` 原本檢查「參考剝削的收益 > 2 SE」。修正後失敗(0.56 vs 2 × 0.84)。診斷 [確認]:
- **修正前，這個檢查其實沒有測到漏洞**:同樣的 300 局，沒有漏洞(機率 0)時收益 1.26,完整漏洞時 1.33。「每次都最小加注」的剝削策略本來就贏過 40 次訓練的策略，和漏洞無關。
- 修正後 all-in 要以完整籌碼攤牌，變異數變大(SE 0.60 → 0.84),這個巧合的餘裕就沒了。
- 改成：同樣的牌局與 seed,有漏洞的收益要大於沒漏洞的(0.56 > −0.67)。這是固定 seed 的方向檢查，不是顯著性檢定;測試裡已註明。真正的檢測力用 `scripts.inspect_sbr_power` 在正式 checkpoint 上量(A2 第 13 節)。
- [推測] A2 在 v1 上量到的檢測力結果是舊規則下的;新規則的 checkpoint 出來後應重跑一次 power test。

### 7.7 之後
- C1:新解 `hu_d5_full_bucket_s20_e70`(同樣設定)從 0 訓練;舊的 `hu_d5_full_bucket_s20` 在 manifest 標為舊規則、只留作對照。指令見 `docs/PENDING_RUNS.md`。
- A2:新 8k 出來後跑 standard 評估;v1 / v2 的報告是舊規則下的結果。
