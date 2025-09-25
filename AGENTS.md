# AGENTS.md (Refactored Plan)

This document updates the **agent structure** of **The Clockwork Heist** to reflect the proposed single‑file refactor. The game remains easy to upload (still one file), but internally it is now **modularized by section** with clear headers.

---

## File Structure (Single File Organization)
The code is organized top‑to‑bottom into sections:

```python
# ===============================
# Imports & Constants
# ===============================

# ===============================
# Utility Functions
# ===============================

# ===============================
# Agents
# ===============================
class CrewAgent: ...
class ToolAgent: ...
class HeistAgent: ...
class CityAgent: ...
class ArcManager: ...

# ===============================
# Game Manager & UI
# ===============================
class GameManager: ...

# ===============================
# Entry Point
# ===============================
if __name__ == "__main__":
    main()
```

---

## CrewAgent
**Purpose**: Represents crew members and resolves skill checks.

- Same responsibilities as before.
- Fix: `get_crew_member` is the single source of truth.
- Leveling & XP thresholds remain.

---

## ToolAgent
**Purpose**: Provides tool effects from `game_data.json`.

- No change in responsibilities.
- Clearly grouped in **Agents** section.

---

## HeistAgent
**Purpose**: Runs full heists, events, and outcomes.

- **Refactor Changes:**
  - `self.last_heist_successful` added (exposed to other systems).
  - Tool/ability tracking reset at the start of each heist.
  - `_apply_effects` now consistently calls `crew_agent.get_crew_member`.
  - Rescue heist frees crew **only if** the heist succeeds.

---

## CityAgent
**Purpose**: Global player state.

- **Refactor Changes:**
  - `unlocked_heists` saved and loaded.
  - Loot, reputation, treasury unchanged.

---

## ArcManager
**Purpose**: Manages story arcs and narrative events.

- **Refactor Changes:**
  - Uses `completed_triggers` to guard against repeating the same event (e.g., Watch crackdown).
  - Narrative events remain inline with `print` + `input` flow.

---

## GameManager
**Purpose**: Central loop, menus, save/load.

- **Refactor Changes:**
  - Menu system grouped cleanly.
  - Crew roster shows from `crew_agent.crew_members` (fix).
  - Healing resets crew status to `"active"`.
  - Save/load handles `unlocked_heists`.

---

## Entry Point
**Purpose**: Keeps file upload simple.

- Game launches with:
  ```python
  if __name__ == "__main__":
      gm = GameManager()
      gm.start_game()
  ```

---

## Benefits of This Refactor
- **Clarity**: Each class lives in its own clearly marked section.
- **Consistency**: All state transitions use the same values (e.g., `active`, `injured`, `arrested`).
- **Robustness**: Fixes to roster, healing, rescue, tool resets, and save/load.
- **Upload‑Friendly**: Still just one `main.py` file, no external Python modules.

---

## Next Steps
- Optionally add inline docstrings for each agent.
- (Future) Split into true modules once portability is no longer required.

