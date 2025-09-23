# AGENTS.md

This file describes the core agents/tools used in **The Clockwork Heist**, how they interact, and their input/output conventions. These align with the current `game_data.json` structure.

---

## CrewAgent
**Purpose**: Represents individual crew members (Rogues, Mages, Artificers, etc.). Handles skill checks and stores base stats.

- **Inputs**: 
  - Crew `id` (e.g., `"rogue_1"`)
  - Skill check type (e.g., `"stealth"`, `"magic"`)
  - Difficulty for the check
- **Outputs**: 
  - `True` or `False` for success/failure of the skill check.
- **Notes**: 
  - This agent is a straightforward data container and skill check resolver.
  - **Unique Abilities**: Crew members now have unique abilities (e.g., Gambler's reroll, Scout's forewarning). The logic for these abilities is handled by the `HeistAgent` during a heist.

---

## ToolAgent
**Purpose**: Manages tools and their effects. It parses the `effect` string from `game_data.json` into a structured format for the `HeistAgent`.

- **Method**: `get_tool_effect(tool_id, crew_role)`
- **Inputs**:
  - Tool `id` (e.g., `"tool_lockpick"`)
  - The `role` of the crew member using the tool.
- **Outputs**:
  - A dictionary describing the tool's effect. Examples:
    - `{'type': 'bonus', 'skill': 'lockpicking', 'value': 2}`
    - `{'type': 'difficulty_reduction', 'condition': 'guard-related', 'value': 2}`
    - `{'type': 'bypass', 'check': 'lockpicking', 'notoriety': 2}`
- **Notes**:
  - The `HeistAgent` is responsible for interpreting this dictionary and applying the effect.
  - This agent uses regular expressions to parse the effect strings.

---

## HeistAgent
**Purpose**: Orchestrates a complete heist sequence, including random events and unique crew abilities.

- **Inputs**:
  - Heist `id` (e.g., `"heist_1"`)
  - A list of crew `id`s.
  - A dictionary of tool assignments (`{crew_id: tool_id}`).
- **Internal State (during `run_heist`)**:
  - `abilities_used_this_heist`: A `set` to track which crew members have used their "once per heist" ability.
  - `double_loot_active`: A boolean flag set by the Gambler's successful reroll.
- **Key Logic**:
  - **Random Events**: Has a chance to inject a random event into the heist's event queue.
  - **Ability Handling**:
    - **Scout**: Checks for the scout before a random event is announced.
    - **Alchemist**: Prompts the user to use the +1 bonus before each event.
    - **Gambler**: Prompts the user to reroll after a failed check.
  - **Tool Integration**: Calls `ToolAgent.get_tool_effect()` and applies the resulting logic (bonuses, difficulty reduction, bypasses).
- **Outputs**:
  - A fully narrated heist sequence printed to the console.
  - Updates to the `CityAgent` (loot and notoriety).

---

## CityAgent
**Purpose**: Tracks global player state within Brasshaven.

- **Inputs**:
  - Updates from HeistAgent (loot gained, notoriety changes)
- **Outputs**:
  - Updated player state (stored in `player` object from JSON)
- **Notes**:
  - MVP keeps this simple: just `starting_notoriety` and `starting_loot`.

---

## GameManager
**Purpose**: Central controller that manages the overall game flow, including the main menu and persistence.

- **Key Logic**:
  - **Save/Load**: At startup, prompts the user to start a new game or load from `save_game.json`.
  - **Main Menu**: Presents a persistent menu to the player with options to:
    - `[P]lan Heist`: Initiates the heist setup sequence.
    - `[S]ave Game`: Saves the current notoriety and loot.
    - `[E]xit Game`: Terminates the application.
  - **Delegation**: Coordinates all the other agents to run the game.

---

## Example Flow (Phase 2)
1.  **GameManager** starts, asks user to **[N]ew Game** or **[L]oad Game**.
2.  The main menu is displayed. Player chooses **[P]lan Heist**.
3.  **GameManager** guides the player through choosing a heist, crew (e.g., including the Alchemist and Gambler), and assigning tools.
4.  **GameManager** calls **HeistAgent.run_heist()**.
5.  **HeistAgent** begins the event sequence.
    - Before an event, it sees the Alchemist is available and asks: `Use Alchemist's 'Shielding Elixir'? [Y/N]`. Player inputs `Y`.
    - The skill check for the event fails.
    - **HeistAgent** sees the Gambler is available and asks: `Use Gambler's 'Double or Nothing' to reroll? [Y/N]`. Player inputs `Y`.
    - The reroll succeeds. The heist continues, and a flag is set to double the loot.
6.  The heist finishes successfully. **HeistAgent** calls **CityAgent** to add the (doubled) loot.
7.  Control returns to the **GameManager**'s main menu. Player can choose to **[S]ave Game**.
8.  Player chooses **[E]xit Game**.

---