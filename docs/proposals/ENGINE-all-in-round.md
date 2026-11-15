# 提案：面對 all-in 的玩家沒有機會行動(遊戲引擎 bug)

狀態:**待你核准**(day69,D1 實作時發現)。修正會改變遊戲規則的行為，所有現有 checkpoint 都要重訓。

標記:**[確認]** = 程式或實測確認;**[推測]** = 推論。

## 1. 現象 [確認]
單挑、籌碼 20、盲注 1 / 2、ante 1.5,button = seat 0。BTN 在根節點 all-in(加到 20):
- 遊戲**直接進入換牌**,輪到 BB 換牌。BB 本輪只投入 2、手上還有 16.5,沒有 all-in,**從頭到尾沒有機會跟注或棄牌**。
- 換牌後也沒有下注，直接攤牌。輸贏只有 BB 原本投入的部分:3 個 seed 的結果是 BTN +3.5 / +3.5 / −2.0。BTN 多下的 16.5 沒有被跟注，退還給 BTN。
- 對照：加注到 8.9(不是 all-in)時,BB 正常輪到行動。

重現:`tests/test_known_bugs.py`(標成 strict xfail,目前會「如預期地失敗」)。

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
