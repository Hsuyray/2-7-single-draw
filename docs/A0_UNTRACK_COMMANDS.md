# A0: commands to stop tracking generated files (you decide; nothing here was run)

`.gitignore` only affects **untracked** files. The files below are already tracked, so git keeps tracking them until you remove them from the index. `git rm --cached` removes them from the index only: **local files stay on disk**, and **history is not rewritten** (old commits still contain them, so the repo size does not shrink).

Counts measured on this branch after adding the new `.gitignore` (`git ls-files -ci --exclude-standard`): 2,048 tracked files now match an ignore rule.

| Group | Tracked files |
|---|---|
| `.venv/` | 1,892 |
| `__pycache__/*.pyc` under `solver/`, `scripts/`, `tests/` | 151 |
| `checkpoints/production_v2_maxdraw5_40k.chk.gz.tmp` (52.9 MB, left by the killed 40k run) | 1 |
| `experiments/*.chk.gz` (`eq_off`, `eq_on`, `guard_smoke`, `p0_small`; scratch outputs from `RUN_INSTRUCTIONS.md`) | 4 |

Production checkpoints in `checkpoints/*.chk.gz` are **not** ignored and not in this list.

## Steps (PowerShell, repo root, on a clean working tree)

1. Dry run first. This prints what would be removed and changes nothing:
   ```powershell
   git rm -r --cached -n .venv | Measure-Object -Line
   git ls-files -ci --exclude-standard | Measure-Object -Line     # expect ~2048
   ```
2. Untrack the virtual environment:
   ```powershell
   git rm -r --cached -q .venv
   ```
3. Untrack everything else that the new `.gitignore` matches (bytecode, `.tmp`, scratch checkpoints):
   ```powershell
   git ls-files -ci --exclude-standard | git rm --cached -q --pathspec-from-file=-
   ```
4. Check, then commit:
   ```powershell
   git status --short | Select-String "^D" | Measure-Object -Line   # ~2048 staged removals
   Test-Path .venv\Scripts\python.exe                                # must be True: files still on disk
   git ls-files -ci --exclude-standard | Measure-Object -Line        # must be 0
   git commit -m "day34: stop tracking venv, bytecode, temp and scratch checkpoint files"
   ```
5. Confirm that a normal run no longer dirties the tree:
   ```powershell
   python -m pytest tests -q
   git status --short        # expect empty
   ```

Undo before committing: `git restore --staged .` (re-adds the index entries; nothing on disk changed).

## Open decision: where the large checkpoints should live

Current sizes: `production_v2_maxdraw5_v2.chk.gz` 59.0 MB, `production_v2_maxdraw5.chk.gz` 29.5 MB, `production_v1.chk.gz` 9.9 MB. GitHub warns above 50 MB per file and rejects above 100 MB, and a solution library (WS C1: several stack depths) will exceed that. Options:

| Option | Pros | Cons |
|---|---|---|
| Keep in git | Nothing to change | Each new version adds to the repo permanently; a file over 100 MB cannot be pushed |
| GitHub Releases (upload as assets, 2 GB per file) | Keeps the repo small; versioned with tags | Manual or scripted download step |
| Git LFS for `checkpoints/*.chk.gz` going forward (`git lfs track`) | Transparent in the workflow | Free quota is small (about 1 GB storage / 1 GB bandwidth per month); migrating existing files means rewriting history, which is **not** recommended here |

Suggestion, not applied: keep the existing files as they are, publish new solution-library checkpoints as Release assets, and record each checkpoint's config, seed and evaluation report in a manifest (WS C1). Add `checkpoints/` to `.gitignore` only after that is in place.
