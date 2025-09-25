import json
import random

CHEAT_MODE = True  # Toggle this to False for normal play

class CrewAgent:
    # Adding outcome constants for clarity
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"

    def __init__(self, crew_data, progression_data):
        self.crew_members = {c['id']: c for c in crew_data}
        self.progression_data = progression_data

    def get_crew_member(self, crew_id):
        return self.crew_members.get(crew_id)

    def add_xp(self, crew_id, xp_amount):
        """Adds XP to a crew member and checks for level ups."""
        member = self.get_crew_member(crew_id)
        if not member:
            return False

        member['xp'] += xp_amount
        leveled_up = False

        xp_thresholds = self.progression_data['xp_thresholds']

        # Using a while loop in case of multiple level-ups from a large XP gain
        while member['level'] < self.progression_data['level_cap'] and member['xp'] >= xp_thresholds[member['level']]:
            member['level'] += 1
            leveled_up = True
            print(f"[Progression] {member['name']} has reached Level {member['level']}!")

        return leveled_up

    def perform_skill_check(self, crew_id, skill, difficulty, partial_success_margin=1, roll=None, tool_bonus=0, temporary_effects=None):

        crew_member = self.get_crew_member(crew_id)
        if not crew_member:
            # Consistent return type, and a helpful debug message
            print(f"[Warning] perform_skill_check: crew '{crew_id}' not found.")
            return self.FAILURE

        if temporary_effects is None:
            temporary_effects = {}

        base_skill_value = crew_member['skills'].get(skill, 0)
        # safe lookup for temporary modifier
        temp_modifier = temporary_effects.get(crew_id, {}).get(skill, 0)
        effective_skill = base_skill_value + temp_modifier

        if roll is None:
            roll = random.randint(1, 10)

        total_skill = effective_skill + tool_bonus + roll

        print(f"  > {crew_member['name']} attempts {skill} check (Difficulty: {difficulty})")
        if temp_modifier != 0:
            print(f"  > Base Skill: {base_skill_value} (Modified to {effective_skill} by temporary effect)")
        else:
            print(f"  > Skill: {base_skill_value}")
        print(f"  > + Tool/Ability Bonus: {tool_bonus} + Roll: {roll} = Total: {total_skill}")

        if total_skill >= difficulty:
            return self.SUCCESS
        elif total_skill >= difficulty - partial_success_margin:
            return self.PARTIAL
        else:
            return self.FAILURE


class ToolAgent:
    def __init__(self, tool_data):
        self.tools = {t['id']: t for t in tool_data}

    def get_tool_effect(self, tool_id, crew_role):
        tool = self.tools.get(tool_id)
        if not (tool and crew_role in tool['usable_by']):
            return {}

        # Since the JSON is now uniform, we can just return the effect object directly.
        # The isinstance check is a good safeguard in case other data formats are ever added.
        if isinstance(tool['effect'], dict):
            return tool['effect']
        
        # Return empty if the effect is not a dictionary, preventing errors.
        return {}

    def validate_tool_usage(self, tool_id, crew_role):
        tool = self.tools.get(tool_id)
        return tool and crew_role in tool['usable_by']

class HeistAgent:
    def __init__(self, heist_data, random_events_data, special_events_data, crew_agent, tool_agent, city_agent):
        self.heists = {h['id']: h for h in heist_data}
        self.random_events = random_events_data
        self.special_events = {e['id']: e for e in special_events_data}
        self.crew_agent = crew_agent
        self.tool_agent = tool_agent
        self.city_agent = city_agent

        # Persistent defaults so methods like _apply_effects can be called anytime
        self.tools_used_this_heist = {}            # shape: { crew_id: { tool_id: used_count } }
        self.abilities_used_this_heist = set()
        self.temporary_effects = {}                # shape: { crew_id: { skill: modifier } }
        self.double_loot_active = False
        self.arcane_reservoir_stored = False
 

    # New helper method in HeistAgent
    def _apply_effects(self, effects, crew_ids, active_crew_id, total_loot=None):
        """Applies a list of effect objects to the game state."""
        if not effects:
            return

        for effect in effects:
            etype = effect.get('type')

            if etype == 'add_notoriety':
                self.city_agent.increase_notoriety(effect.get('value', 1))

            elif etype == 'update_reputation':
                self.city_agent.update_reputation(effect['rep_type'], effect['value'])

            elif etype == 'set_status':
                target_id = active_crew_id if effect.get('who') == 'active_member' else random.choice(crew_ids)
                member = self.crew_agent.get_crew_member(target_id)
                if member:
                    member['status'] = effect['status']
                    print(f"  > [Effect Applied!] {member['name']} is now {effect['status']}!")
                    # Unlock rescue heist if someone is arrested
                    if effect['status'] == 'arrested':
                        if "rescue_heist" not in self.city_agent.unlocked_heists:
                            self.city_agent.unlocked_heists.add("rescue_heist")
                            print("[Heist Unlocked] Rescue Heist is now available to free your crew!")

            elif etype == 'lose_loot':
                scope = effect.get('scope')
                if scope == 'half' and total_loot:
                    half = len(total_loot) // 2
                    del total_loot[:half]
                elif scope == 'primary' and total_loot:
                    total_loot.pop(0)
                else:
                    amount = effect.get('amount', effect.get('value', 1))
                    for _ in range(amount):
                        if total_loot:
                            total_loot.pop()

            elif etype == 'set_faction_hostile':
                faction = effect.get('faction')
                if faction == 'random':
                    faction = random.choice(list(self.city_agent.factions.keys()))
                self.city_agent.factions[faction]['standing'] = -999
                print(f"[Faction] {self.city_agent.factions[faction]['name']} is now hostile!")


            elif etype == 'modify_xp':
                target_id = active_crew_id if effect.get('who') == 'active_member' else random.choice(crew_ids)
                member = self.crew_agent.get_crew_member(target_id)
                if member:
                    value = effect.get('value', 0)
                    member['xp'] += value
                    print(f"  > [Effect Applied!] {member['name']}'s XP is modified by {value}!")

            elif etype == 'temp_debuff':
                target_ids = []
                who = effect.get('who')
                if who == 'all_members':
                    target_ids = crew_ids
                elif who == 'active_member':
                    target_ids = [active_crew_id]
                elif who == 'random_member':
                    target_ids = [random.choice(crew_ids)]
                # This part for role-based targeting needs to be a loop
                elif 'role' in effect:
                    for crew_id in crew_ids:
                        member = self.crew_agent.get_crew_member(crew_id)
                        if member and member['role'].lower() == effect['role'].lower():
                            target_ids.append(crew_id)

                for target_id in target_ids:
                    if target_id not in self.temporary_effects:
                        self.temporary_effects[target_id] = {}
                    skill = effect['skill']
                    value = effect['value']
                    self.crew_agent.crew_members.get(target_id)
                    print(f"  > [Effect Applied!] {member['name']}'s {skill} is temporarily modified by {value}!")
            # Add more effect types here as needed (e.g., 'give_loot', 'lose_loot')
    
    
    def run_heist(self, heist_id, crew_ids, tool_assignments):
        heist = self.heists.get(heist_id)
        if not heist:
            print("Heist not found.")
            return []

        # --- Initialize Heist State ---
        print(f"\n--- Starting Heist: {heist['name']} ---")
        total_loot = []
        self.tools_used_this_heist = {}
        self.abilities_used_this_heist = set()
        self.temporary_effects = {} # Tracks temporary stat penalties for the heist
        self.double_loot_active = False
        self.arcane_reservoir_stored = False # Tracks stored success for the Mage

        # Heist outcome tracking
        event_outcomes = {'success': 0, 'partial': 0, 'failure': 0}

        # --- Event Generation ---
        events_to_run = list(heist['events'])

        # Heist-level Notoriety Scaling
        if 'scaling' in heist and self.city_agent.notoriety >= heist['scaling'].get('notoriety_threshold', 999):
            if 'extra_event' in heist['scaling']:
                extra_event_id = heist['scaling']['extra_event']
                if extra_event_id in self.special_events:
                    print(f"[Notoriety Effect] Your reputation precedes you, drawing out a dangerous foe!")
                    events_to_run.append(self.special_events[extra_event_id])


        # --- Random Event Check ---
        avoid_random_event = False
        for crew_id in crew_ids:
            member = self.crew_agent.get_crew_member(crew_id)
            if 'scout_eagle_of_brasshaven' in member['upgrades']:
                print("[Eagle of Brasshaven] Finn's vigilance allows the crew to bypass an unforeseen complication!")
                avoid_random_event = True
                self.abilities_used_this_heist.add('eagle_of_brasshaven')
                break

        if not avoid_random_event and self.random_events and random.randint(1, 4) == 1:
            random_event = random.choice(self.random_events).copy()

            if 'reputation_hook' in random_event:
                fear = self.city_agent.reputation['fear']
                respect = self.city_agent.reputation['respect']
                if fear > respect:
                    random_event['difficulty'] += 1
                    print(f"[Reputation Effect] Your fearsome reputation makes this situation more volatile! (Difficulty +1)")
                elif respect > fear:
                    random_event['difficulty'] -= 1
                    print(f"[Reputation Effect] Your respectable reputation gives you an edge. (Difficulty -1)")

            random_event['description'] = f"[Random Event] {random_event['description']}"
            random_event.setdefault('success', {"text": "The crew handled the unexpected situation."})
            random_event.setdefault('failure', {"text": "The event causes a complication.", "effects": [{"type": "add_notoriety", "value": 1}]})

            scout_present = 'scout_1' in crew_ids
            if scout_present and 'scout_1' not in self.abilities_used_this_heist:
                print(f"\n[Scout's Forewarning!] Finn Ashwhistle spots trouble ahead.")
                print(f"  > Upcoming Event: {random_event['description']}")
                self.abilities_used_this_heist.add('scout_1')
            else:
                print(f"\n[A random event occurs during the heist!]")

            insert_pos = random.randint(0, len(events_to_run))
            events_to_run.insert(insert_pos, random_event)

        # --- Main Event Loop ---
        for event in events_to_run:
            # --- Arcane Reservoir Spend ---
            mage_member = self.crew_agent.get_crew_member('mage_1')
            if ('mage_1' in crew_ids and self.arcane_reservoir_stored and
                    'mage_arcane_reservoir' in mage_member['upgrades']):
                use_ability = input(f"\n* Event: {event['description']}\n  > Use Lyra's stored success from the Arcane Reservoir to auto-succeed? [Y/N]: ").upper()
                if use_ability == 'Y':
                    print("  > [Arcane Reservoir] Lyra releases the stored magical success, effortlessly resolving the situation.")
                    self.arcane_reservoir_stored = False
                    event_outcomes['success'] += 1
                    continue

            rogue_member = self.crew_agent.get_crew_member('rogue_1')
            if ('rogue_1' in crew_ids and
                    'rogue_ghost_in_gears' in rogue_member['upgrades'] and
                    'ghost_in_the_gears' not in self.abilities_used_this_heist):

                use_ability = input(f"\n* Event: {event['description']}\n  > Use Silas's 'Ghost in the Gears' to bypass this event completely? [Y/N]: ").upper()
                if use_ability == 'Y':
                    print("  > [Ghost in the Gears] Silas finds a hidden path, and the crew slips past the challenge entirely.")
                    self.abilities_used_this_heist.add('ghost_in_the_gears')
                    event_outcomes['success'] += 1
                    continue

            print(f"\n* Event: {event['description']}")
            
            # --- Pre-Check Abilities (Event-Wide Buffs) ---
            event_wide_bonus = 0
            
            # Alchemist Ability Check
            alchemist_member = self.crew_agent.get_crew_member('alchemist_1')
            if ('alchemist_1' in crew_ids and 'alchemist_1' not in self.abilities_used_this_heist):
                use_ability = input(f"  > Use Alchemist's 'Shielding Elixir' for a +1 bonus to all crew checks in this event? [Y/N]: ").upper()
                if use_ability == 'Y':
                    event_wide_bonus += 1
                    self.abilities_used_this_heist.add('alchemist_1')
                    print("  > [Alchemist's Elixir] The crew feels invigorated by the potion!")
            
            # Artificer "Clockwork Legion" Check
            artificer_member = self.crew_agent.get_crew_member('artificer_1')
            if ('artificer_1' in crew_ids and
                    'artificer_clockwork_legion' in artificer_member['upgrades'] and
                    'clockwork_legion' not in self.abilities_used_this_heist):
                use_ability = input(f"  > Use Dorian's 'Clockwork Legion' for a +2 bonus to all crew checks in this event? [Y/N]: ").upper()
                if use_ability == 'Y':
                    event_wide_bonus += 2
                    self.abilities_used_this_heist.add('clockwork_legion')
                    print(f"  > [Clockwork Legion] A swarm of tiny clockwork helpers aids the crew!")

            # Find best crew member, accounting for temporary effects
            best_crew_id = None
            best_skill = -99 # Start low to account for negative skills
            for crew_id in crew_ids:
                member = self.crew_agent.get_crew_member(crew_id)
                if member:
                    temp_modifier = self.temporary_effects.get(crew_id, {}).get(event['check'], 0)
                    effective_skill = member['skills'].get(event['check'], 0) + temp_modifier
                    if effective_skill > best_skill:
                        best_skill = effective_skill
                        best_crew_id = crew_id

            if not best_crew_id:
                print("No suitable crew member for this event! It automatically fails.")
                event_outcomes['failure'] += 1
                continue

            difficulty = event['difficulty']

            # Event-level Notoriety Scaling
            if 'scaling' in event and self.city_agent.notoriety >= event['scaling'].get('notoriety_threshold', 999):
                if 'difficulty_increase' in event['scaling']:
                    increase = event['scaling']['difficulty_increase']
                    difficulty += increase
                    print(f"  > [Notoriety Effect] The stakes are higher! (Difficulty +{increase})")

            crew_member = self.crew_agent.get_crew_member(best_crew_id)

            # --- Requirement Check ---
            requirements = event.get("requirements", {})
            required_value = requirements.get(event['check'])
            # Check against base skill, not temporarily modified skill
            if required_value and crew_member['skills'].get(event['check'], 0) < required_value:
                print(f"  > {crew_member['name']} is too inexperienced! Needs {required_value} {event['check']} (has {crew_member['skills'].get(event['check'], 0)}).")
                event_outcomes['failure'] += 1
                continue
            
            # --- Single-Check Abilities (like Tinker's Edge) ---
            tinker_bonus = 0
            if 'artificer_1' in crew_ids:
                if ('artificer_tinkers_edge' in artificer_member['upgrades'] and
                        'tinkers_edge' not in self.abilities_used_this_heist):
                    use_ability = input(f"  > Use Dorian's 'Tinker's Edge' for a +2 bonus on this specific check? [Y/N]: ").upper()
                    if use_ability == 'Y':
                        print(f"  > [Tinker's Edge] Dorian quickly assembles a gadget to help {crew_member['name']}!")
                        tinker_bonus = 2
                        self.abilities_used_this_heist.add('tinkers_edge')
            
            # Total bonus for the check
            total_bonus = event_wide_bonus + tinker_bonus

            # --- Dice Roll & Tool Handling ---
            roll = random.randint(1, 10)
            bypass_check = False
            tool_bonus = 0

            tool_id = tool_assignments.get(best_crew_id)
            if tool_id:
                effect = self.tool_agent.get_tool_effect(tool_id, crew_member['role'])
                if effect:
                    tool = self.tool_agent.tools[tool_id]
                    # Per-crew mapping: tools_used_this_heist[crew_id] -> { tool_id: used_count }
                    crew_tool_usage = self.tools_used_this_heist.get(best_crew_id, {})
                    used = crew_tool_usage.get(tool_id, 0)
                    uses_left = tool.get('uses_per_heist', 1) - used

                    if uses_left > 0:
                        # Bonus that matches the event check; allow 'any' in tool effect too
                        if effect.get('type') == 'bonus' and (effect.get('skill') == event['check'] or effect.get('skill') == 'any'):
                            tool_bonus = effect['value']
                            self.tools_used_this_heist.setdefault(best_crew_id, {})[tool_id] = used + 1
                            print(f"  > {crew_member['name']} uses {tool['name']} for a +{tool_bonus} bonus.")
                        elif effect.get('type') == 'difficulty_reduction':
                            condition = effect.get('condition', '').replace('-', ' ')
                            if condition in event['description'].lower():
                                difficulty -= effect['value']  # reduce the check difficulty
                                self.tools_used_this_heist.setdefault(best_crew_id, {})[tool_id] = used + 1
                                print(f"  > {crew_member['name']} uses {tool['name']} to lower the difficulty by {effect['value']}.")
                        elif effect.get('type') == 'bypass' and effect.get('check') == event['check']:
                            bypass_check = True
                            self.city_agent.increase_notoriety(effect.get('notoriety', 0))
                            self.tools_used_this_heist.setdefault(best_crew_id, {})[tool_id] = used + 1
                            print(f"  > {crew_member['name']} uses {tool['name']} to bypass the check, gaining {effect.get('notoriety',0)} notoriety!")
                        elif effect.get('type') == 'special' and effect.get('id') == 'alchemy_craft':
                            use_kit = input(f"  > Use Alchemy Kit to brew a potion for the whole crew this event? [Y/N]: ").upper()
                            if use_kit == 'Y':
                                potion_type = input("    Choose potion type: [S]tealth, [C]ombat, [M]agic: ").upper()
                                chosen_type = {"S": "stealth", "C": "combat", "M": "magic"}.get(potion_type, "any")
                                event_wide_bonus += 1
                                self.tools_used_this_heist.setdefault(best_crew_id, {})[tool_id] = used + 1
                                print(f"  > {crew_member['name']} brews a {chosen_type} elixir! All crew gain +1 for this event.")
                                # Backfire check
                                if random.randint(1, 6) == 1:
                                    print("  > [Alchemy Backfire!] The elixir sputters and fumes! The Watch takes notice. Notoriety +1.")
                                    self.city_agent.increase_notoriety(1)

                        print(f"  > {crew_member['name']} uses {tool['name']}. ({max(0, uses_left - 1)} uses left)")
                    else:
                        print(f"  > {crew_member['name']} has no uses left for {tool['name']}.")


            # --- Ability Check (from Level-Up Upgrades) ---
            auto_succeed = False
            if (event['check'] == 'stealth' and
                'rogue_shadowstep' in crew_member['upgrades'] and
                'rogue_shadowstep' not in self.abilities_used_this_heist):
                use_ability = input(f"  > Use {crew_member['name']}'s 'Shadowstep' to automatically succeed? [Y/N]: ").upper()
                if use_ability == 'Y':
                    # ... logic
                    self.abilities_used_this_heist.add('rogue_shadowstep')


            # Perform Check
            result = self.crew_agent.FAILURE
            if bypass_check or auto_succeed:
                result = self.crew_agent.SUCCESS
            else:
                result = self.crew_agent.perform_skill_check(
                    best_crew_id,
                    event['check'],
                    difficulty,
                    roll=roll,
                    tool_bonus=total_bonus + tool_bonus,
                    temporary_effects=self.temporary_effects
                )

            # Gambler Ability Check
            if result == self.crew_agent.FAILURE:
                gambler_present = 'gambler_1' in crew_ids
                if gambler_present and 'gambler_1' not in self.abilities_used_this_heist:
                    use_ability = input(f"  > A setback! Use Gambler's 'Double or Nothing' to reroll? [Y/N]: ").upper()
                    if use_ability == 'Y':
                        self.abilities_used_this_heist.add('gambler_1')
                        print("  > [Gambler's Wager] Cassian Vey is betting it all on a second chance!")
                        reroll_result = self.crew_agent.perform_skill_check(best_crew_id, event['check'], difficulty, temporary_effects=self.temporary_effects)
                        if reroll_result == self.crew_agent.SUCCESS:
                            print("  > Reroll Success! The gamble paid off spectacularly!")
                            result = self.crew_agent.SUCCESS
                            self.double_loot_active = True
                        else:
                            print("  > Reroll Failure! The house always wins. Notoriety increases sharply.")
                            self.city_agent.increase_notoriety(2)
                
                mage_member = self.crew_agent.get_crew_member('mage_1')
                if ('mage_1' in crew_ids and
                        'mage_chronoward' in mage_member['upgrades'] and
                        'chronoward' not in self.abilities_used_this_heist):
                    use_ability = input(f"  > A critical failure! Use Lyra's 'Chronoward' to rewind time and reroll? [Y/N]: ").upper()
                    if use_ability == 'Y':
                        print("  > [Chronoward] Time shimmers and resets around the failed action!")
                        self.abilities_used_this_heist.add('chronoward')
                        new_result = self.crew_agent.perform_skill_check(
                            best_crew_id,
                            event['check'],
                            difficulty,
                            tool_bonus=total_bonus + tool_bonus,
                            temporary_effects=self.temporary_effects
                        )
                        result = new_result

            # Resolve Outcome
            outcome = None
            if result == self.crew_agent.SUCCESS:
                event_outcomes['success'] += 1
                outcome = event.get('success', {"text": "The crew succeeded."})

                # --- Arcane Reservoir Store ---
                mage_member = self.crew_agent.get_crew_member('mage_1')
                if ('mage_1' in crew_ids and
                        'mage_arcane_reservoir' in mage_member['upgrades'] and
                        not self.arcane_reservoir_stored and # Can't store if one is already held
                        'arcane_reservoir_store' not in self.abilities_used_this_heist): # Can only store once
                    store_success = input("  > Store this success in Lyra's Arcane Reservoir for later use? [Y/N]: ").upper()
                    if store_success == 'Y':
                        self.arcane_reservoir_stored = True
                        self.abilities_used_this_heist.add('arcane_reservoir_store')
                        print("  > [Arcane Reservoir] The moment of success is captured and stored.")

                self.temporary_effects.clear()

            elif result == self.crew_agent.PARTIAL:
                event_outcomes['partial'] += 1
                outcome = event.get('partial_success', {"text": "The crew managed, but with a complication."})
                self.temporary_effects.clear()

            else: # Failure
                event_outcomes['failure'] += 1
                outcome = event.get('failure', {"text": "The crew failed."})
                self.temporary_effects.clear()

            # Unified outcome resolution
            if outcome:
                print(f"  > {result.title()}: {outcome['text']}")
                self._apply_effects(outcome.get('effects'), crew_ids, best_crew_id, total_loot)
                self.temporary_effects.clear()


        
        # --- Distinct Getaway Phase ---
        getaway = heist.get('getaway')
        if getaway:
            print(f"\n--- Getaway: {getaway['name']} ---")
            print(f"{getaway['description']}")

            # Select best crew for getaway
            best_id, best_skill = None, -99
            for crew_id in crew_ids:
                member = self.crew_agent.get_crew_member(crew_id)
                if member:
                    skill_val = member['skills'].get(getaway['check'], 0)
                    if skill_val > best_skill:
                        best_skill, best_id = skill_val, crew_id

            if not best_id:
                print("No suitable crew for the getaway. Automatic failure!")
                result = self.crew_agent.FAILURE
            else:
                result = self.crew_agent.perform_skill_check(
                    best_id,
                    getaway['check'],
                    getaway['difficulty'],
                    temporary_effects=self.temporary_effects
                )

            # Determine which outcome object to use based on the result
            outcome_key = "partial_success" if result == "partial" else result
            outcome = getaway.get(outcome_key, {})


            # Print the descriptive text for the player
            print(f"  > {result.title()}: {outcome['text']}")
            
            # Apply the structured effects
            self._apply_effects(outcome.get('effects'), crew_ids, best_id, total_loot)

        
        
        # --- Heist Resolution ---
        leveled_up_crew = []
        heist_successful = event_outcomes['failure'] == 0
        self.last_heist_successful = heist_successful

        if heist_successful:
            print("\n--- Heist Successful! ---")
            xp_gain = heist.get("xp_success", 8)
            if self.double_loot_active:
                print("[Gambler's Reward] The loot is doubled!")
            for loot_item in heist['potential_loot']:
                self.city_agent.add_loot(loot_item)
                total_loot.append(loot_item)
                if self.double_loot_active:
                    self.city_agent.add_loot(loot_item)
                    total_loot.append(loot_item)
        else:
            print("\n--- Heist Failed! ---")
            xp_gain = heist.get("xp_fail", 1)

        print(f"\n[Crew Report] Each participating member gains {xp_gain} XP.")
        for crew_id in crew_ids:
            if self.crew_agent.add_xp(crew_id, xp_gain):
                leveled_up_crew.append(crew_id)

        print(f"Final Notoriety: {self.city_agent.notoriety}")
        print(f"Total Loot Acquired: {[item['item'] for item in total_loot]}")

        return leveled_up_crew


class CityAgent:
    def __init__(self, player_data):
        self.notoriety = player_data.get('notoriety', 0)
        self.loot = list(player_data.get('starting_loot', []))
        self.reputation = player_data.get('reputation', {"fear": 0, "respect": 0})
        # Initialize factions (NEW)
        self.factions = {f['id']: {"standing": f['standing'], "name": f['name']}
                         for f in player_data.get('factions', [])}
        self.unlocked_heists = set([h['id'] for h in player_data.get('starting_heists', [])])
        self.heists_completed = 0
        self.treasury = 100
        self.tool_inventory = player_data.get('tool_inventory', {})



    def increase_notoriety(self, amount=1):
        self.notoriety += amount
        print(f"[City Update] Notoriety increased to {self.notoriety}")

    def treasury_value(self):
        return self.treasury


    def update_reputation(self, rep_type, amount):
        if rep_type in self.reputation:
            self.reputation[rep_type] += amount
            if amount > 0:
                print(f"[City Update] Your reputation for {rep_type} has increased to {self.reputation[rep_type]}.")
            else:
                print(f"[City Update] Your reputation for {rep_type} has decreased to {self.reputation[rep_type]}.")

    def add_loot(self, item):
        self.loot.append(item)
        print(f"[City Update] Loot acquired: {item['item']} (Value: {item['value']})")

class ArcManager:
    def __init__(self, arcs_data, narrative_events, special_events, city_agent, crew_agent):
        self.arcs = arcs_data
        self.narrative_events = {e['id']: e for e in narrative_events}
        self.special_events = {e['id']: e for e in special_events}
        self.city_agent = city_agent
        self.crew_agent = crew_agent
        self.completed_triggers = set()  # prevent repeating the same stage

    def check_arcs(self):
        """Check all arcs against current game state."""
        for arc in self.arcs:
            for idx, stage in enumerate(arc.get('stages', [])):
                # skip if stage is not a dict (defensive)
                if not isinstance(stage, dict):
                    continue

                # stable trigger key using arc id + stage index
                trigger_id = f"{arc['id']}:stage_{idx}"
                if trigger_id in self.completed_triggers:
                    continue

                # Notoriety threshold stage
                if 'threshold' in stage:
                    try:
                        threshold = int(stage['threshold'])
                    except (TypeError, ValueError):
                        continue
                    if self.city_agent.notoriety >= threshold:
                        self._fire_stage(stage)
                        self.completed_triggers.add(trigger_id)
                        continue

                # Faction hostile all
                if stage.get("trigger") == "faction_hostile_all":
                    if all(f['standing'] < 0 for f in self.city_agent.factions.values()):
                        self._fire_stage(stage)
                        self.completed_triggers.add(trigger_id)
                        continue

                # Crew level trigger (e.g., "rogue_1 level >= 2")
                trigger_text = stage.get("trigger", "")
                if "level" in trigger_text:
                    parts = trigger_text.split()
                    if len(parts) >= 4:
                        crew_id = parts[0]
                        try:
                            level_required = int(parts[3])
                        except ValueError:
                            continue
                        member = self.crew_agent.get_crew_member(crew_id)
                        if member and member.get('level', 0) >= level_required:
                            self._fire_stage(stage)
                            self.completed_triggers.add(trigger_id)
                            continue


    def _fire_stage(self, stage):
        """Resolve event or special from a stage."""
        if "event" in stage:
            event_id = stage['event']
            if event_id in self.narrative_events:
                event = self.narrative_events[event_id]
                self._present_narrative_event(event)
        elif "special" in stage:
            special_id = stage['special']
            if special_id in self.special_events:
                event = self.special_events[special_id]
                print(f"\n[Special Event Triggered] {event['description']}")
                if "effect" in event and "unlock_heist" in event["effect"]:
                    heist_id = event["effect"]["unlock_heist"]
                    if heist_id not in self.city_agent.unlocked_heists:
                        self.city_agent.unlocked_heists.add(heist_id)
                        print(f"[Heist Unlocked] {heist_id} is now available!")


    def _present_narrative_event(self, event):
        """Simple console choice system for narrative events."""
        print(f"\n--- Narrative Event ---")
        print(event['description'])
        if 'choices' in event:
            for i, choice in enumerate(event['choices']):
                print(f"  [{i+1}] {choice['text']}")
            choice_idx = -1
            while choice_idx < 1 or choice_idx > len(event['choices']):
                try:
                    choice_idx = int(input("Choose: "))
                except ValueError:
                    continue
            chosen = event['choices'][choice_idx-1]
            self._apply_effects(chosen.get('effects', {}))

    def _apply_effects(self, effects):
        """Very simple parser for choice effects."""
        if 'loot' in effects:
            if effects['loot'] > 0:
                self.city_agent.add_loot({"item": "Unknown Loot", "value": int(effects['loot'])})
            else:
                # remove loot by value if negative
                loss = abs(int(effects['loot']))
                removed = 0
                while self.city_agent.loot and removed < loss:
                    self.city_agent.loot.pop()
                    removed += 1
                print(f"[Effect] Lost {loss} loot.")

        if 'respect' in effects:
            self.city_agent.update_reputation('respect', int(effects['respect']))
        if 'fear' in effects:
            self.city_agent.update_reputation('fear', int(effects['fear']))
        if 'faction' in effects:
            for f, delta in effects['faction'].items():
                try:
                    delta = int(str(delta).replace("+", ""))  # handles "+2", "2", -1
                except ValueError:
                    print(f"[Warning] Could not parse faction effect {f}: {delta}")
                    continue
                self.city_agent.factions[f]['standing'] += delta
                print(f"[Faction Update] {f} standing changed by {delta}.")




class GameManager:
    def __init__(self):
        with open('game_data.json', 'r', encoding='utf-8') as f:
            self.game_data = json.load(f)

        self.city_agent = CityAgent(self.game_data['player'])
        self.crew_agent = CrewAgent(self.game_data['crew_members'], self.game_data['progression'])
        self.tool_agent = ToolAgent(self.game_data['tools'])
        self.heist_agent = HeistAgent(
            self.game_data['heists'],
            self.game_data['random_events'],
            self.game_data['special_events'],
            self.crew_agent,
            self.tool_agent,
            self.city_agent
        )
        self.arc_manager = ArcManager(
            self.game_data['campaign_arcs'],
            self.game_data['narrative_events'],
            self.game_data['special_events'],
            self.city_agent,
            self.crew_agent
        )


        if CHEAT_MODE:
            self.enable_cheat_mode()


    def save_game(self, filename="save_game.json"):
        save_data = {
            "notoriety": self.city_agent.notoriety,
            "loot": self.city_agent.loot,
            "crew_members": list(self.crew_agent.crew_members.values()),
            "reputation": self.city_agent.reputation,
            "heists_completed": self.city_agent.heists_completed,
            "tool_inventory": self.city_agent.tool_inventory,
            "unlocked_heists": list(self.city_agent.unlocked_heists),
            "factions": self.city_agent.factions,                # NEW
            "completed_triggers": list(self.arc_manager.completed_triggers)
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=4)
        print(f"\n[Game saved to {filename}.]")

    def load_game(self, filename="save_game.json"):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                save_data = json.load(f)

            self.city_agent.notoriety = save_data['notoriety']
            self.city_agent.loot = save_data['loot']
            saved_crew = save_data.get('crew_members', [])
            self.crew_agent.crew_members = {c['id']: c for c in saved_crew}
            self.crew_agent = CrewAgent(list(self.crew_agent.crew_members.values()), self.game_data['progression'])
            self.city_agent.reputation = save_data.get('reputation', {"fear": 0, "respect": 0})

            # Restore factions (NEW)
            self.city_agent.factions = save_data.get('factions', self.city_agent.factions)

            # Restore arc triggers (NEW)
            self.arc_manager.completed_triggers = set(save_data.get('completed_triggers', []))
            self.city_agent.heists_completed = save_data.get("heists_completed", 0)
            self.city_agent.tool_inventory = save_data.get("tool_inventory", {})

            # Restore unlocked heists if present; otherwise use defaults
            saved_unlocked = save_data.get("unlocked_heists")
            if saved_unlocked is not None:
                self.city_agent.unlocked_heists = set(saved_unlocked)

            # If any crew are arrested on load, make sure rescue_heist is available
            if any(m.get("status") == "arrested" for m in self.crew_agent.crew_members.values()):
                self.city_agent.unlocked_heists.add("rescue_heist")



            print(f"[Game loaded from {filename}.]")

            # Re-init crew agent so XP/levels sync properly
            self.crew_agent = CrewAgent(list(save_data['crew_members'].values()), self.game_data['progression'])
            return True
        except FileNotFoundError:
            return False
        except (KeyError, json.JSONDecodeError):
            print("[Save file is corrupted. Starting a new game.]")
            return False

    def start_game(self):
        print("Welcome to The Clockwork Heist!")
        print("="*30)

        choice = input("Start [N]ew Game or [L]oad Game? ").upper()
        if choice == 'L':
            if not self.load_game():
                print("No save file found. Starting a new game.")

        while True:
            # Watch crackdown if notoriety is too high — but only once
            if self.city_agent.notoriety >= 12 and "arrest_triggered" not in self.arc_manager.completed_triggers:
                arrest_event = self.heist_agent.special_events.get('event_arrest')
                if arrest_event:
                    # Apply the "failure" effects of the Watch crackdown to a random crew member
                    crew_ids = list(self.crew_agent.crew_members.keys())
                    if crew_ids:
                        target = random.choice(crew_ids)
                        self.heist_agent._apply_effects(arrest_event['failure']['effects'], crew_ids=[target])
                        print("The Watch has cracked down! One of your crew has been arrested...")
                    # Mark as handled so it won't repeat
                    self.arc_manager.completed_triggers.add("arrest_triggered")




            print("\n--- Main Menu ---")
            print(f"Notoriety: {self.city_agent.notoriety} | Reputation: Fear {self.city_agent.reputation['fear']}, Respect {self.city_agent.reputation['respect']}")

            current_loot = "None"
            if self.city_agent.loot:
                current_loot = ', '.join([item['item'] for item in self.city_agent.loot])
            print(f"Loot: {current_loot}")

            print("\n[P]lan Heist")
            print("[C]rew Roster") # A good place to see crew details
            print("[M]arket / Hideout") # The new loot sink
            print("[F]action Status") 
            print("[S]ave Game")
            print("[E]xit Game")

            # Arrested crew options
            arrested_members = [m for m in self.crew_agent.crew_members.values() if m.get("status") == "arrested"]
            if arrested_members:
                if arrested_members:
                    print(f"\n[Alert] a member was arrested!")
                target_name = arrested_members[0]['name']
                print(f"[B]ribe the Watch: Pay gold to free {target_name}")
                if "rescue_heist" in self.city_agent.unlocked_heists:
                    print(f"[R]escue Mission: Break {target_name} out of the Watch Barracks!")

            
            action = input("> ").upper()

            if action == 'P':
                self.plan_and_execute_heist()
            elif action == 'S':
                self.save_game()
            elif action == 'F':
                self.show_faction_status()
            elif action == 'M':
                self.show_market_menu() # A new method you would need to create

            elif action == 'C':
                self.show_crew_roster()

            elif action == 'B':
                self._bribe_for_release()

            elif action == 'R':
                self._attempt_rescue_heist()

            elif action == 'E':
                print("\nYou melt back into the shadows of Brasshaven...")
                break
            else:
                print("Invalid choice. Please try again.")

    def show_crew_roster(self):
        print("\n=== Crew Roster ===")
        members = self.crew_agent.crew_members  # FIX: correct source
        if not members:
            print("No crew members found.")
            return
        for m in members.values():
            name = m.get("name", "Unknown")
            role = m.get("role", "Unknown")
            status = m.get("status", "active")
            lvl = m.get("level", 1)
            xp = m.get("xp", 0)
            skills = m.get("skills", {})
            print(f"- {name} [{role}] — Status: {status} — Lv {lvl} ({xp} XP) — Skills: {skills}")


    
    
    def _handle_level_ups(self, leveled_up_crew_ids):
        if not leveled_up_crew_ids:
            return

        print("\n--- Crew Progression ---")
        for crew_id in leveled_up_crew_ids:
            member = self.crew_agent.get_crew_member(crew_id)
            print(f"\n{member['name']} has leveled up and can learn a new skill!")

            # Get available upgrades
            general_upgrades = self.game_data['progression']['upgrade_options']['general']
            role_upgrades = self.game_data['progression']['upgrade_options'].get(member['role'].lower(), [])
            available_upgrades = general_upgrades + role_upgrades

            print("Choose an upgrade:")
            for i, upgrade in enumerate(available_upgrades):
                print(f"  [{i+1}] {upgrade['text']}")

            # Get player choice
            choice = -1
            while choice < 1 or choice > len(available_upgrades):
                try:
                    choice_str = input(f"Enter number (1-{len(available_upgrades)}): ")
                    choice = int(choice_str)
                except ValueError:
                    print("Invalid input.")

            # ... inside _handle_level_ups ...
            selected_upgrade_obj = available_upgrades[choice - 1]

            # Store the unique ID or the descriptive text. Storing the ID is better.
            member['upgrades'].append(selected_upgrade_obj['id']) 
            print(f"{member['name']} has learned: '{selected_upgrade_obj['text']}'!")

            # Apply effects immediately
            if 'effects' in selected_upgrade_obj:
                for effect in selected_upgrade_obj['effects']:
                    if effect.get('type') == 'stat_boost':
                        skill = effect['skill']
                        value = effect['value']
                        member['skills'][skill] += value
                        print(f"[Skill Increased] {member['name']}'s {skill} is now {member['skills'][skill]}.")

    def show_market_menu(self):
        """Handles spending loot: healing crew, buying tools, and fencing treasures."""
        while True:
            print("\n--- The Black Market ---")
            print(f"Treasury: {self.city_agent.treasury_value()} coin.")
            print(f"Loot Inventory: {[item['item'] for item in self.city_agent.loot] or 'None'}")
            print("[1] Heal Injured Crew")
            print("[2] Buy Tools")
            print("[3] Fence Loot (convert treasures into coin)")
            print("[4] Return to Main Menu")
            choice = input("> ").strip()

            if choice == "1":
                self._heal_injured_crew()
            elif choice == "2":
                self._buy_tools()
            elif choice == "3":
                self._fence_loot()
            elif choice == "4":
                break
            else:
                print("Invalid choice.")


    def _attempt_rescue_heist(self):
        print("\nThe Watch Barracks rise from Brasshaven’s steel heart, bristling with riflemen and clockwork hounds.")
        print("Breaking in is madness — but loyalty runs deeper than fear. Tonight, you attempt the impossible: a prison break.")

        arrested = [m for m in self.crew_agent.crew_members.values() if m.get('status') == "arrested"]
        if not arrested:
            print("No crew are under arrest.")
            return
        print("A risky prison break to free your ally...")
        crew_ids = [cid for cid, m in self.crew_agent.crew_members.items() if m.get("status", "active") == "active"]
        if not crew_ids:
            print("No active crew available for the rescue!")
            return
        # Simplify: pick active crew automatically or let player choose
        tool_assignments = {}
        self.heist_agent.run_heist("rescue_heist", crew_ids[:2], tool_assignments)
        # If successful: free one arrested member
        if getattr(self.heist_agent, "last_heist_successful", False):
            arrested_members = [m for m in self.crew_agent.crew_members.values() if m.get('status') == "arrested"]
            if arrested_members:
                freed = arrested_members[0]
                freed['status'] = "active"
                print(f"{freed['name']} has been freed from the Watch!")
        else:
            print("The rescue failed. Your captured crew remain imprisoned for now.")


    
    def _bribe_for_release(self):
        arrested = [m for m in self.crew_agent.crew_members.values() if m.get('status') == "arrested"]
        if not arrested:
            print("No crew are under arrest.")
            return
        cost = 100 + (self.city_agent.notoriety * 5)
        print(f"Bribe cost: {cost} coin OR 1 loot item per crew member.")
        for m in arrested:
            if self.city_agent.treasury < cost:
                if self.city_agent.loot:
                    pay_loot = input(f"Not enough coin. Trade 1 loot item instead? [Y/N]: ").upper()
                    if pay_loot == "Y":
                        loot_item = self.city_agent.loot.pop(0)  # could let player choose later
                        m['status'] = "active"
                        print(f"{m['name']} is freed after the Watch accepts '{loot_item['item']}' as hush payment.")
                    else:
                        print("You leave them in the cells for now...")


    
    def _fence_loot(self):
        if not self.city_agent.loot:
            print("You have no treasures to fence.")
            return

        # --- Calculate multiplier from faction data ---
        multiplier = 1.0
        for faction_id, faction in self.city_agent.factions.items():
            data = next((f for f in self.game_data["factions"] if f["id"] == faction_id), None)
            if not data:
                continue

            mods = data.get("fencing_modifiers", {})
            standing = faction.get("standing", 0)

            if standing >= 3 and "allied" in mods:
                multiplier *= mods["allied"]
                print(f"[Faction Bonus] {data['name']} (Allied): x{mods['allied']}")
            elif standing > 0 and "friendly" in mods:
                multiplier *= mods["friendly"]
                print(f"[Faction Bonus] {data['name']} (Friendly): x{mods['friendly']}")
            elif standing <= -3 and "hostile" in mods:
                multiplier *= mods["hostile"]
                print(f"[Faction Penalty] {data['name']} (Hostile): x{mods['hostile']}")

        # --- Fence Menu ---
        print("\n--- Fence Loot ---")
        for i, item in enumerate(self.city_agent.loot, 1):
            adj_value = int(item['value'] * multiplier)
            print(f"[{i}] {item['item']} (Base: {item['value']} → Fencing: {adj_value} coin)")

        choice = input("Choose loot to fence (number), 'all', or 'back': ").strip()
        if choice == "back":
            return

        if choice == "all":
            total = sum(int(item['value'] * multiplier) for item in self.city_agent.loot)
            self.city_agent.treasury += total
            self.city_agent.loot.clear()
            print(f"All loot fenced for {total} coin! Treasury: {self.city_agent.treasury}")
            return

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(self.city_agent.loot):
                item = self.city_agent.loot.pop(idx)
                adj_value = int(item['value'] * multiplier)
                self.city_agent.treasury += adj_value
                print(f"Fenced {item['item']} for {adj_value} coin. Treasury: {self.city_agent.treasury}")
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input.")




    def _heal_injured_crew(self):
        injured = [m for m in self.crew_agent.crew_members.values() if m.get("status") == "injured"]
        if not injured:
            print("No crew members are injured.")
            return

        healing_cost = self.game_data["market"]["healing_cost"]

        print("\n--- Healing Services ---")
        for i, member in enumerate(injured, 1):
            print(f"[{i}] {member['name']} - Heal for {healing_cost} coin (You have {self.city_agent.treasury})")

        choice = input("Choose crew to heal (number) or 'back': ").strip()
        if choice == "back":
            return

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(injured):
                member = injured[idx]
                if self._spend_loot(healing_cost):
                    member["status"] = "active"
                    print(f"{member['name']} has been healed and is ready for the next heist!")
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input.")


    def _buy_tools(self):
        tools_for_sale = self.game_data["market"]["tools"]

        print("\n--- Tools for Sale ---")
        tool_ids = list(tools_for_sale.keys())
        for i, tool_id in enumerate(tool_ids, 1):
            tool = self.tool_agent.tools[tool_id]
            price = tools_for_sale[tool_id]["price"]
            owned = self.city_agent.tool_inventory.get(tool_id, 0)
            print(f"[{i}] {tool['name']} - {price} coin (Owned: {owned})")

        choice = input("Choose tool to buy (number) or 'back': ").strip()
        if choice == "back":
            return

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(tool_ids):
                tool_id = tool_ids[idx]
                tool = self.tool_agent.tools[tool_id]
                price = tools_for_sale[tool_id]["price"]

                if self._spend_loot(price):
                    self.city_agent.tool_inventory[tool_id] = self.city_agent.tool_inventory.get(tool_id, 0) + 1
                    print(f"Purchased {tool['name']}! You now own {self.city_agent.tool_inventory[tool_id]}.")
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input.")



    def _spend_loot(self, amount):
        """Try to spend treasury coin. Returns True if successful."""
        if self.city_agent.treasury < amount:
            print("Not enough coin!")
            return False

        self.city_agent.treasury -= amount
        print(f"Spent {amount} coin. Treasury now: {self.city_agent.treasury}")
        return True




    def show_faction_status(self):
        """Displays current standings with Brasshaven factions."""
        print("\n--- Faction Status ---")
        for fid, faction in self.city_agent.factions.items():
            standing = faction.get('standing', 0)
            name = faction.get('name', fid)
            # Determine reputation label
            if standing >= 3:
                rep = "Allied"
            elif standing <= -3:
                rep = "Hostile"
            elif standing > 0:
                rep = "Friendly"
            elif standing < 0:
                rep = "Unfriendly"
            else:
                rep = "Neutral"
            print(f"{name}: Standing {standing} ({rep})")
        input("\nPress Enter to return to the main menu...")

    def enable_cheat_mode(self):
        print("[CHEAT MODE ENABLED] Story progression testing active.")

        # 2. Buff crew so all checks succeed
        for member in self.crew_agent.crew_members.values():
            for skill in member['skills']:
                member['skills'][skill] = 10

        # 3. Start factions at NEUTRAL (not hostile yet!)
        self.city_agent.factions = {
            "guilds": {"standing": 0},
            "nobles": {"standing": 0},
            "syndicates": {"standing": 0},
        }

        # 4. Start with notoriety 0 (let it rise naturally)
        self.city_agent.notoriety = 0

    
    def plan_and_execute_heist(self):
        print("\nAvailable Heists:")
        for heist_id, heist in self.heist_agent.heists.items():
            # Skip rescue heist here — it’s handled separately in the Main Menu
            if heist_id == "rescue_heist":
                continue
            if heist_id in self.city_agent.unlocked_heists or not heist_id.startswith("heist_finale_"):
                print(f"  [{heist_id}] {heist['name']} (Difficulty: {heist['difficulty']})")

        chosen_heist_id = input("Choose a heist to attempt (or 'back' to return): ")
        if chosen_heist_id == 'back':
            return
        if chosen_heist_id not in self.heist_agent.heists:
            print("Invalid heist ID. Returning to Main Menu.")
            return

        # 2. Select Crew
        print("\nAvailable Crew Members:")
        xp_thresholds = self.game_data['progression']['xp_thresholds']
        for crew_id, crew in self.crew_agent.crew_members.items():
            level = crew['level']
            xp = crew['xp']
            next_lvl_xp = xp_thresholds[level] if level < len(xp_thresholds) else "MAX"
            status = crew.get('status', 'active')

            if status == "injured":
                print(f"  [X] {crew['name']} ({crew['role']}) - Injured, unavailable")
            elif status == "arrested":
                print(f"  [X] {crew['name']} ({crew['role']}) - Arrested by the Watch!")
            else:
                print(f"  [{crew_id}] {crew['name']} ({crew['role']}) - "
                    f"Lvl: {level} ({xp}/{next_lvl_xp} XP) - Skills: {crew['skills']}")


        chosen_crew_ids_str = input("Select your crew (e.g., rogue_1,mage_1): ")
        chosen_crew_ids = [c.strip() for c in chosen_crew_ids_str.split(',')]

        for crew_id in chosen_crew_ids:
            member = self.crew_agent.get_crew_member(crew_id)
            if member and member.get('status') == 'injured':
                print(f"[Invalid Crew] {member['name']} is injured and cannot join the heist. Please plan again.")
                return # Abort the heist planning
            if member.get('status') == 'arrested':
                print(f"[Invalid Crew] {member['name']} has been arrested by the Watch! Bribe or rescue them first.")
                return  # Abort the heist planning

        heist = self.heist_agent.heists[chosen_heist_id]
        required_roles = heist.get("required_roles", [])
        max_party_size = heist.get("max_party_size", len(required_roles))

        # Verify crew size
        if len(chosen_crew_ids) > max_party_size:
            print(f"You can only bring up to {max_party_size} crew members.")
            return

        # Verify required roles are included
        crew_roles = [self.crew_agent.get_crew_member(c_id)['role'] for c_id in chosen_crew_ids]
        if not all(role in crew_roles for role in required_roles):
            print(f"This heist requires: {', '.join(required_roles)}. You must include them.")
            return
        
        
        # 3. Assign Tools
        tool_assignments = {}
        self.heist_agent.tools_used_this_heist = {}
        if not self.city_agent.tool_inventory:
            print("\nNo tools available in inventory.")
        else:
            print("\nAvailable Tools in Inventory:")
            for i, (tool_id, count) in enumerate(self.city_agent.tool_inventory.items(), 1):
                tool = self.tool_agent.tools[tool_id]
                print(f"[{i}] {tool['name']} (Owned: {count}, Usable by: {', '.join(tool['usable_by'])})")

            for crew_id in chosen_crew_ids:
                member = self.crew_agent.get_crew_member(crew_id)
                choice = input(f"Assign a tool to {member['name']} (or 0 to remove):").strip()
                if choice.lower() == "none":
                    continue

                try:
                    idx = int(choice) - 1
                    tool_ids = list(self.city_agent.tool_inventory.keys())
                    if 0 <= idx < len(tool_ids):
                        tool_id = tool_ids[idx]

                        # ✅ Here’s your snippet in action:
                        if self.city_agent.tool_inventory.get(tool_id, 0) > 0:
                            tool_assignments[crew_id] = tool_id
                            print(f"{member['name']} will take {self.tool_agent.tools[tool_id]['name']} into the heist.")
                        else:
                            print("That tool is no longer available.")
                    else:
                        print("Invalid choice. Skipping tool assignment.")
                except ValueError:
                    print("Invalid input. Skipping tool assignment.")

        # --- Confirmation before starting heist ---
        print("\n--- Heist Preparation Complete ---")
        print(f"Crew selected: {[self.crew_agent.get_crew_member(cid)['name'] for cid in chosen_crew_ids]}")
        if tool_assignments:
            assigned_list = [self.tool_agent.tools[tid]["name"] for tid in tool_assignments.values()]
            print(f"Tools assigned: {', '.join(assigned_list)}")
        else:
            print("Tools assigned: None")

        choice = input("Proceed with the heist? (yes/no): ").strip().lower()
        if choice != "yes":
            print("Heist canceled. Returning to hideout...")
            return
        
        # Deduct tools only now, after confirmation
        for crew_id, tool_id in tool_assignments.items():
            if tool_id in self.city_agent.tool_inventory:
                self.city_agent.tool_inventory[tool_id] -= 1
                if self.city_agent.tool_inventory[tool_id] <= 0:
                    del self.city_agent.tool_inventory[tool_id]

            # Initialize per-heist uses
            tool_data = self.tool_agent.tools[tool_id]
            max_uses = tool_data.get("uses_per_heist", 1)
            if crew_id not in self.heist_agent.tools_used_this_heist:
                self.heist_agent.tools_used_this_heist[crew_id] = {}
            self.heist_agent.tools_used_this_heist[crew_id][tool_id] = max_uses


        
        
        # 4. Run Heist
        leveled_up_crew = self.heist_agent.run_heist(chosen_heist_id, chosen_crew_ids, tool_assignments)
        
        self.city_agent.heists_completed += 1
        
        if leveled_up_crew:
            self._handle_level_ups(leveled_up_crew)

        # After resolving a heist, check for story progression
        self.arc_manager.check_arcs()



if __name__ == "__main__":
    game = GameManager()
    game.start_game()
