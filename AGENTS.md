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

# Phase 3 – Strategic Depth (AGENTS.md)

These updates expand the agents to support Phase 3 features: **Notoriety**, **Crew Progression**, **Reputation**, and **Complex Outcomes**. They are written to align with the Brasshaven lore of shifting power, rival crews, and the city’s memory of its thieves.

---

## CityAgent (Updated)
**Purpose**: Tracks global player state within Brasshaven, now reflecting how the city reacts to the crew’s infamy or influence.

- **New State**:
  - `notoriety`: Integer, rises when alarms are raised, explosives are used, or guards are killed. High notoriety draws elite clockwork enforcers or rival syndicates.
  - `reputation`: Dictionary with two values:
    - `fear`: Increases when the crew uses brutal or reckless tactics.
    - `respect`: Increases when the crew pulls off clean, clever heists.
  - The balance of fear vs respect determines how guilds, nobles, and syndicates respond to the crew.
- **Integration**:
  - Updates after each heist via HeistAgent.
  - Influences difficulty scaling and NPC reactions in future heists.
  - Updates XP and level progression by applying rules from the new `progression` block in `game_data.json`.

---

## CrewAgent (Updated)
**Purpose**: Represents crew members, now with progression over multiple heists.

- **New State**:
  - `xp`: Integer earned from successful events or heists.
  - `level`: Derived from XP thresholds in `progression.xp_thresholds` (data-driven, no longer hardcoded).
  - `upgrades`: Tracks chosen improvements to skills or unique perks.
  - `available_upgrades`: Determined by role-specific options in `progression.upgrade_options`.
- **Lore Note**: Crew members grow their legend in Brasshaven; their names whispered in taverns and alleys as they gain notoriety and skill.

---

## HeistAgent (Updated)
**Purpose**: Orchestrates heists with more complex outcomes and scaling challenges.

- **New Logic**:
  - **Partial Success**: Events may now contain a `partial_success` key with a mixed outcome (e.g., loot reduced, notoriety gained, or crew injury).
  - **Betrayal Events**: Certain outcomes may trigger betrayal (e.g., a rival syndicate turning a contact, or even the Gambler selling out the crew if reputation is too low).
  - **Arrest Outcomes**: High notoriety failures may result in crew members being captured. They are unavailable until the crew mounts a rescue or pays a ransom.
  - **Difficulty Scaling**: Event objects may now include a `scaling` field that raises difficulty or adds extra events when notoriety thresholds are passed.
- **Integration with Reputation**:
  - High **fear** may cause guards to flee but attract deadlier enemies.
  - High **respect** may open alternate, easier paths (e.g., sympathetic workers opening side doors).

---

## Example Flow (Phase 3)
1. **CityAgent** starts tracking notoriety (2) and reputation (fear: 3, respect: 1).
2. The crew plans the **Royal Treasury Heist**.
3. In **HeistAgent**, an event resolves as a **partial success**: they slip past guards but drop some loot.
4. The **Gambler** rerolls a failure, succeeds, and doubles loot—but notoriety spikes.
5. Because notoriety ≥ 10, **elite clockwork riflemen** spawn as reinforcements (from an event with `scaling`).
6. The heist ends. **CrewAgent** updates: each member gains XP, Scout levels up and improves stealth using an option from `progression.upgrade_options`.
7. **CityAgent** records that nobles now fear the crew; syndicates may reach out with more dangerous opportunities.

---

### Notes
- These expansions remain modular. Agents don’t need rewriting—only extensions.
- `game_data.json` now contains a `progression` block that defines XP thresholds, level caps, and available upgrades. Agents should reference this instead of hardcoding rules.
- Event objects now support `partial_success` and `scaling` fields, and HeistAgent must process them dynamically.