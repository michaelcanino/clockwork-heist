# AGENTS.md

This file describes the core agents/tools used in **The Clockwork Heist** MVP, how they interact, and their input/output conventions. These align with the current `game_data.json` structure.

---

## CrewAgent
**Purpose**: Represents individual crew members (Rogues, Mages, Artificers). Handles skill checks, tool usage, and outcomes during heists.

- **Inputs**: 
  - Crew `id` (e.g., `"rogue_1"`)
  - Action or skill check type (e.g., `"stealth"`, `"magic"`)
  - Optional tool assignment
- **Outputs**: 
  - Success/failure result
  - Narrative outcome string
  - Updated crew status (e.g., injury flag)
- **Notes**: 
  - Skills map directly to JSON fields: `stealth`, `lockpicking`, `combat`, `magic`.

---

## ToolAgent
**Purpose**: Manages tools and their effects when assigned to crew members.

- **Inputs**:
  - Tool `id` (e.g., `"tool_lockpick"`)
  - Target crew member `id`
- **Outputs**:
  - Adjusted skill check values (temporary boost)
  - Validation if tool is usable by crew role (from `usable_by` field)
- **Notes**:
  - Tools only provide bonuses during the specific event/skill check.

---

## HeistAgent
**Purpose**: Orchestrates a heist sequence.

- **Inputs**:
  - Heist `id` (e.g., `"heist_1"`)
  - Crew assignments
  - Tool assignments
- **Outputs**:
  - Heist summary (success/failure, loot acquired, notoriety changes)
  - Event outcomes (success/failure strings, crew injuries)
- **Notes**:
  - Reads from JSON `heists` array
  - Processes each event in order using skill checks + random roll modifiers

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
**Purpose**: Central controller that coordinates agents and player input.

- **Inputs**:
  - Player choices (select crew, assign tools, choose heist)
- **Outputs**:
  - Narration text for events
  - Final heist results
- **Notes**:
  - Loads and parses `game_data.json`
  - Delegates to CrewAgent, ToolAgent, and HeistAgent in sequence

---

## Example Input/Output Flow (MVP)
1. **Player Input**: Choose heist → select crew → assign tools.
2. **GameManager** calls **HeistAgent** with selections.
3. **HeistAgent** runs through `events`:
   - For each, calls **CrewAgent** skill check (+ **ToolAgent** bonus if assigned).
   - Success/failure returns narration + state changes.
4. **HeistAgent** finalizes outcome → passes notoriety/loot updates to **CityAgent**.
5. **GameManager** prints summary to player.

---

# Phase 2 – Replayability & QoL

## Expanded Crew Roster
- Add new crew members with **unique traits**:
  - Gambler → Risk/reward ability (can double rewards or lose them).
  - Alchemist → Can craft potions that mitigate failures.
  - Scout → Provides forewarning about upcoming random events.

## Multiple Heist Locations
- Introduce several new heist settings:
  - The Merchant’s Guild (mid-tier difficulty, high gold payout).
  - The Royal Treasury (high difficulty, rare loot).
  - The Abandoned Cathedral (medium difficulty, cursed loot with trade-offs).

## More Tools
- Add new tools to diversify strategies:
  - **Explosives** → Break into vaults but increase notoriety.
  - **Disguise Kit** → Lower difficulty of guard-related events.
  - **Alchemy Kit** → Exclusive for Alchemist, allows buffing crew stats.

## Random Events
- Create a pool of random events to increase replayability:
  - Guard patrols.
  - Traps (poison darts, collapsing floor).
  - Rival thieves interfering mid-heist.
  - Environmental hazards (fire, flooding).

## Save/Load System
- Implement a basic persistence system:
  - Save current crew, tools, loot, and notoriety.
  - Load state from file to continue progress.

---
### Notes for Implementation
- Keep events modular to support future expansions.
- Balance crew traits so no single strategy dominates.
- Save system can start with simple JSON persistence.