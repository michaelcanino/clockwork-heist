# AGENTS.md

This document describes the core agents used in **The Clockwork Heist** and how they interact. It is updated to reflect the current `main.py` and `game_data.json`.

---

## CrewAgent
**Purpose**: Represents individual crew members and resolves skill checks during heists.

- **Inputs**: 
  - Crew `id` (e.g., `"rogue_1"`)
  - Skill check type (e.g., `"stealth"`, `"magic"`)
  - Difficulty of the check
- **Outputs**: 
  - One of: `"success"`, `"partial"`, `"failure"`
- **Behavior**:
  - Computes the effective skill using base skill, temporary modifiers, tools, and random rolls.
  - Tracks XP, levels, and unlockable upgrades based on thresholds from `progression.xp_thresholds`.
  - Applies temporary debuffs (e.g., `"combat –1 until healed"`) parsed from event text.
- **Notes**:
  - Unique crew abilities (e.g., Shadowstep, Chronoward) are triggered and managed by `HeistAgent`, not `CrewAgent`.

---

## ToolAgent
**Purpose**: Provides structured tool effects from the `game_data.json`.

- **Method**: `get_tool_effect(tool_id, crew_role)`
- **Inputs**:
  - Tool `id` (e.g., `"tool_lockpick"`)
  - Crew member `role`
- **Outputs**:
  - A dictionary describing the tool’s effect. Examples:
    ```python
    {'type': 'bonus', 'skill': 'lockpicking', 'value': 2}
    {'type': 'difficulty_reduction', 'condition': 'guard', 'value': 2}
    {'type': 'bypass', 'check': 'lockpicking', 'notoriety': 2}
    ```
- **Behavior**:
  - Validates tool usability per crew role.
  - Prevents multiple uses per heist.
- **Notes**:
  - Tool effects are already structured in JSON — no string parsing is needed.

---

## HeistAgent
**Purpose**: Runs full heist sequences, including event resolution, tool use, abilities, and outcomes.

- **Inputs**:
  - Heist `id`
  - List of crew `id`s
  - Tool assignments: `{crew_id: tool_id}`
- **Internal State**:
  - `abilities_used_this_heist`: Tracks “once per heist” ability usage.
  - `temporary_effects`: Stores temporary skill modifiers from partial outcomes.
  - `double_loot_active`: True if Gambler’s reroll succeeds.
  - `arcane_reservoir_stored`: Tracks Mage’s stored success.
- **Key Features**:
  - **Event Sequencing**: Runs main events, inserts random events (25% chance), and notoriety-triggered events.
  - **Difficulty Scaling**: Increases difficulty or adds events when `notoriety` passes thresholds.
  - **Partial Success Handling**: Applies side effects (notoriety, debuffs, loot loss) when outcomes fall just short.
  - **Ability Resolution**: Checks for and prompts use of crew upgrades (e.g., Shadowstep, Clockwork Legion, Chronoward).
  - **Tool Integration**: Applies bonuses, difficulty reductions, bypasses, or notoriety trade-offs.
  - **Special Outcomes**: Injuries, arrests, or unavailable crew handled dynamically.
- **Outputs**:
  - Narrated heist flow printed to console.
  - Updated `CityAgent` state (loot, notoriety, reputation).
  - XP awarded to participating crew.

---

## CityAgent
**Purpose**: Tracks the player’s global state within Brasshaven.

- **State**:
  - `notoriety`: Increases with alarms, bypasses, or failures.
  - `reputation`: Tracks `fear` and `respect` and influences event outcomes.
  - `loot`: Inventory of items gained during heists.
- **Methods**:
  - `increase_notoriety(amount)`
  - `update_reputation(rep_type, amount)`
  - `add_loot(item)`
- **Notes**:
  - High notoriety may spawn special events (e.g., elite enforcers).
  - Fear vs. respect influences random event difficulty and narrative outcomes.

---

## GameManager
**Purpose**: Central controller of the game loop, menus, and persistence.

- **Responsibilities**:
  - Handles save/load from `save_game.json` (including `reputation` and crew state).
  - Main menu options:
    - `[P]lan Heist`: Choose heist, crew, and tools.
    - `[C]rew Roster`: View crew stats and upgrades.
    - `[M]arket`: (WIP) Spend loot and manage resources.
    - `[S]ave Game`: Save progress.
    - `[E]xit Game`: Exit the program.
- **Progression**:
  - After each heist, awards XP and prompts for upgrade selection.
  - Applies chosen skill boosts or unlocks new abilities.

---

## Example Flow
1. **GameManager** starts and loads or initializes the game.
2. The player chooses **[P]lan Heist**.
3. **HeistAgent** executes events, triggering tool effects, crew abilities, and random events.
4. Outcomes (success, partial, failure) modify notoriety, reputation, and crew status.
5. **CityAgent** records loot and updates the city state.
6. **CrewAgent** applies XP and handles level-ups.
7. Control returns to the main menu, allowing the player to save, spend loot, or attempt another heist.

---

# Phase 4 – Factions & Narrative

This phase introduces **factions**, **branching storylines**, and **multi-heist arcs**. These systems layer on top of the existing Crew/Heist/City framework.

---

## FactionAgent
**Purpose**: Represents the major Brasshaven factions and tracks the crew’s standing with them.

- **Factions**:
  - **Guilds** (industry, invention, profit)
  - **Nobles** (wealth, prestige, political power)
  - **Syndicates** (underworld, rival thieves, black markets)

- **State**:
  - Reputation per faction: `allied`, `neutral`, or `hostile`.
  - Favor score (numeric meter, e.g., –10 to +10).
  - Faction perks: discounts, safehouses, unique tools.
  - Faction threats: stronger enemies, assassins, blockades.

- **Integration**:
  - Updated after each heist depending on targets, choices, and outcomes.
  - Influences heist difficulty (e.g., hostile Guild = more automatons).
  - Determines story branches (who offers contracts, betrayals, or alliances).

---

## NarrativeAgent
**Purpose**: Drives branching story events and between-heist narrative choices.

- **Features**:
  - **Between-Heist Events**: Story beats triggered by notoriety, faction standing, or campaign progress.
  - **Choices & Consequences**: Options to ally, betray, or oppose factions.
  - **Event Types**:
    - Dialogue encounters
    - Rumors and intel
    - Faction missions or sabotage requests

- **State**:
  - Tracks key narrative flags (e.g., “betrayed Nobles”, “allied with Syndicates”).
  - Unlocks or locks campaign arcs and heists.

---

## CampaignAgent
**Purpose**: Manages longer arcs across multiple heists.

- **Arcs**:
  - **Faction Rivalries**: Rising tension between Guilds, Nobles, and Syndicates.
  - **Power Balance**: Fear vs. respect shaping how factions treat the crew.
  - **The Clockwork Tower** (optional final arc).

- **Features**:
  - Tracks progress toward arc resolution (e.g., 3–4 faction heists before climax).
  - Modifies available heists dynamically based on alliances or betrayals.
  - Creates “endgame stakes” (e.g., city riots, faction wars, betrayal from within).

---

## Integration Flow
1. **FactionAgent** updates standings after a heist.
2. **NarrativeAgent** injects story events between heists based on standings and reputation.
3. **CampaignAgent** checks arc progression:
   - If thresholds reached → unlock special faction heist.
   - If finale conditions met → unlock **Clockwork Tower** campaign climax.

---

# The Clockwork Tower (Lore Integration)

The **Clockwork Tower** is described in lore as Brasshaven’s central engine of control and power:contentReference[oaicite:1]{index=1}. It would make a strong **final campaign arc**, representing:
- Guild machinery
- Noble wealth
- Syndicate sabotage
- The city itself turning against the crew

**Recommendation**: 
- Don’t drop the Clockwork Tower immediately in Phase 4.
- Instead, **seed it** in faction storylines (rumors, glimpses, blueprints).
- Use Phase 4 for *branching arcs* where factions either push you toward or away from the Tower.
- Save the **Clockwork Tower Heist** as the **Phase 5 / Final Campaign** — the ultimate payoff for choices made in Phase 4.

---

## Future Extensions
- **Side Heists** for arrested crew members (rescue, ransom, or reputation-based outcomes).
- **Market System** to convert loot into upgrades, healing, or notoriety reduction.
- **Crew Assists** allowing secondary members to support checks.

