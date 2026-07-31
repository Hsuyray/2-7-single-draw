# 2-7 Single Draw Solver Architecture v1

## 1. Product Goal

Build a GTO Wizard-style solver and strategy viewer for
2-7 Single Draw.

Users control only:

- Player count: 2 to 6
- Effective stack depth

Game rules are fixed:

- Small blind: 1
- Big blind: 2
- Big blind ante: 1.5

The interface supports:

- Range strategy view
- Exact hand strategy view
- Navigation through user-selected actions


## 2. SolverConfig

A solved game is identified by:

- player_count
- effective_stack

Example:

6-max / 100 BB


## 3. PublicState

PublicState contains only information known to every player.

It includes:

- player count
- effective stack
- button position
- active players
- folded players
- all-in players
- current phase
- acting player
- pot
- current betting round commitments
- public action history
- draw counts already revealed

It must not contain any player's private cards.


## 4. PrivateState

PrivateState contains information visible only to one player.

It includes:

- player identity / position
- five-card hand
- abstract hand representation when abstraction is enabled

PrivateState + PublicState define an InformationState.


## 5. DecisionNode

A DecisionNode represents one public decision point in the game tree.

Examples:

Predraw:

UTG raise
HJ fold
CO fold
BTN fold
SB fold
BB to act

Draw:

UTG raise
BB call
BB draws 1
UTG to draw

Postdraw:

UTG raise
BB call
BB draws 1
UTG draws 1
BB checks
UTG to act


## 6. Strategy

A strategy maps legal actions to probabilities.

Predraw example:

Fold: 0.60
Call: 0.10
Raise: 0.30

Draw example:

Pat: 0.10
Discard K: 0.50
Discard Q,K: 0.30
Discard J,Q,K: 0.10

Postdraw example:

Check: 0.55
Bet: 0.45


## 7. Range Strategy

Range mode returns strategies for every private hand
represented at the current DecisionNode.

Conceptually:

PublicNode
    75432 -> strategy
    87542 -> strategy
    K5432 -> strategy
    24466 -> strategy
    ...


## 8. Hand Strategy

Hand mode takes an exact five-card hand.

Example:

2c 3d 4h 5s Kc

The system:

1. Converts the hand to its InformationState.
2. Finds the strategy at the current DecisionNode.
3. Returns action probabilities.


## 9. State Transition

The user does not manually construct nodes.

The user selects an action.

Example:

Current node:
UTG to act

User selects:
Raise

The engine applies the action and produces the next PublicState.

This continues through:

Predraw betting
-> Draw
-> Postdraw betting
-> Terminal


## 10. Position

Seat numbers are internal engine identifiers.

The product displays poker positions.

Examples:

Heads-up:
BTN/SB
BB

6-max:
UTG
HJ
CO
BTN
SB
BB

Strategies belong to InformationStates, not raw seat numbers.


## 11. Draw Information

Draw decisions are public actions.

For each player the public history records:

- Pat
- Draw 1
- Draw 2
- Draw 3
- etc.

The exact discarded cards remain private.

Therefore:

Villain Pat

and

Villain Draw 1

lead to different future DecisionNodes.


## 12. Strategy Navigation

The UI behaves as a game-tree browser.

Example:

6-max / 100 BB

UTG Raise
-> HJ Fold
-> CO Fold
-> BTN Fold
-> SB Fold
-> BB Call
-> BB Draw 1
-> UTG Draw 1
-> BB Check
-> UTG Strategy

At every decision point the user may switch between:

- Range
- Hand


## 13. Backend Layers

### Game Engine

Responsible for:

- dealing
- betting
- draw actions
- pot handling
- showdown
- state transitions


### Information State

Responsible for:

- public information
- player's private information
- abstraction


### Solver

Responsible for:

- regret updates
- strategy computation
- training


### Strategy Store

Responsible for:

- storing solved strategies
- querying strategies by public node and private hand


### UI

Responsible for:

- selecting player count
- selecting stack
- navigating actions
- displaying range strategy
- displaying hand strategy


## 14. Current Development Order

1. Freeze game rules.
2. Define PublicState.
3. Define PublicNodeKey.
4. Separate public node from private hand information.
5. Add strategy querying.
6. Add range strategy aggregation.
7. Generalize CFR from HU to 2–6 players.
8. Add solved-strategy persistence.
9. Build UI.