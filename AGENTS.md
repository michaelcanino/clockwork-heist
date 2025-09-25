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

# QOL / UX Enhancement Plan for `main.py`

This document lists planned Quality of Life (QOL) and User Experience (UX) improvements for **The Clockwork Heist**.

---

## 1. Streamlined Input Handling
- Add a `get_choice(prompt, options, default=None)` helper.
- Accept both **shortcuts** (e.g., `Y/N`) and **full words** (`Yes/No`).
- Allow **defaults** for smoother play.

```python
def get_choice(prompt, options, default=None):
    options_map = {o[0].upper(): o for o in options}
    while True:
        choice = input(f"{prompt} {options} ").strip().upper()
        if not choice and default:
            return default
        if choice in options_map:
            return options_map[choice]
        if choice in [o.upper() for o in options]:
            return choice.capitalize()
        print(f"Invalid choice. Try again: {options}")
```

---

## 2. Colorized Output for Readability
- Use **Colorama** for cross-platform colored text.
- Green = Success, Yellow = Partial, Red = Failure, Cyan = Notifications.

```python
from colorama import Fore, Style

def format_outcome(result, text):
    if result == "success":
        return f"{Fore.GREEN}✅ Success: {text}{Style.RESET_ALL}"
    elif result == "partial":
        return f"{Fore.YELLOW}⚠️ Partial: {text}{Style.RESET_ALL}"
    else:
        return f"{Fore.RED}❌ Failure: {text}{Style.RESET_ALL}"
```

---

## 3. Crew & Tool Selection UX
- Replace raw ID typing with **numbered menus**.
- Use `choose_from_list()` for crew, tools, or heists.

```python
def choose_from_list(title, items, key="name"):
    print(f"\n-- {title} --")
    for i, item in enumerate(items, 1):
        print(f"[{i}] {item[key]}")
    while True:
        try:
            idx = int(input("Choose number: "))
            if 1 <= idx <= len(items):
                return items[idx-1]
        except ValueError:
            pass
        print("Invalid selection, try again.")
```

---

## 4. Quick Status Summary
- Show **crew status, notoriety, treasury, loot** before each heist.
- Helps decision-making without extra menus.

---

## 5. Auto-Save on Exit & Retry
- Enable **auto-save after every heist**.
- On startup, prompt: `Continue / New Game`.

---

## 6. Narrative Flow Enhancements
- Flavor text after key events:
  - High notoriety → *“The streets whisper your crew’s name...”*
  - Gained respect → *“Word of honor spreads among the Guilds.”*

---

## 7. Skip Repetitive Prompts
- Add **settings toggle** in `GameManager`:
  - `Always Ask`
  - `Auto-Use` (abilities auto-trigger when optimal)

---

## 8. Dice Roll Transparency
- Add toggle to **show/hide dice rolls** for immersion.
- Could be set via `CHEAT_MODE` or a new `DEBUG_MODE` flag.

---

## ✅ Implementation Order
1. Add helper functions (`get_choice`, `choose_from_list`, `format_outcome`).
2. Replace `input()` calls in `HeistAgent` and `GameManager`.
3. Add **status summary panel** before each heist.
4. Integrate **color-coded outcomes**.
5. Enable **auto-save after heists**.
6. Add **narrative flavor lines** for immersion.
7. Implement **ability auto-use settings**.
8. Add **dice transparency toggle**.



