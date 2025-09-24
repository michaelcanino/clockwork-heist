import json
import random
import re

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
        while member['level'] < len(xp_thresholds) and member['xp'] >= xp_thresholds[member['level']]:
            member['level'] += 1
            leveled_up = True
            print(f"[Progression] {member['name']} has reached Level {member['level']}!")

        return leveled_up

    def perform_skill_check(self, crew_id, skill, difficulty, partial_success_margin=1, roll=None, tool_bonus=0, temporary_effects=None):
        crew_member = self.get_crew_member(crew_id)
        if not crew_member:
            return self.FAILURE, "Crew member not found."

        if temporary_effects is None:
            temporary_effects = {}

        base_skill_value = crew_member['skills'].get(skill, 0)
        
        # Apply temporary effects from the heist
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

    def run_heist(self, heist_id, crew_ids, tool_assignments):
        heist = self.heists.get(heist_id)
        if not heist:
            print("Heist not found.")
            return []

        # --- Initialize Heist State ---
        print(f"\n--- Starting Heist: {heist['name']} ---")
        total_loot = []
        self.tools_used_this_heist = set()
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
            if "Eagle of Brasshaven: Automatically avoid the first random event each heist" in member['upgrades']:
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
            random_event.setdefault('success', "The crew handled the unexpected situation.")
            random_event.setdefault('failure', "The event causes a complication. Notoriety increases.")

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
                    'Arcane Reservoir: Store one success to spend later' in mage_member['upgrades']):
                use_ability = input(f"\n* Event: {event['description']}\n  > Use Lyra's stored success from the Arcane Reservoir to auto-succeed? [Y/N]: ").upper()
                if use_ability == 'Y':
                    print("  > [Arcane Reservoir] Lyra releases the stored magical success, effortlessly resolving the situation.")
                    self.arcane_reservoir_stored = False
                    event_outcomes['success'] += 1
                    continue

            rogue_member = self.crew_agent.get_crew_member('rogue_1')
            if ('rogue_1' in crew_ids and
                    'Ghost in the Gears: Once per heist, bypass an entire event with no check' in rogue_member['upgrades'] and
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
                    event_wide_bonus = 1
                    self.abilities_used_this_heist.add('alchemist_1')
                    print("  > [Alchemist's Elixir] The crew feels invigorated by the potion!")
            
            # Artificer "Clockwork Legion" Check
            artificer_member = self.crew_agent.get_crew_member('artificer_1')
            if ('artificer_1' in crew_ids and
                    'Clockwork Legion: Deploys gadgets, granting +2 to all crew checks for one event' in artificer_member['upgrades'] and
                    'clockwork_legion' not in self.abilities_used_this_heist):
                use_ability = input(f"  > Use Dorian's 'Clockwork Legion' for a +2 bonus to all crew checks in this event? [Y/N]: ").upper()
                if use_ability == 'Y':
                    event_wide_bonus = 2
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
                if ('Tinker’s Edge: Craft a temporary gadget granting +2 to any check once per heist' in artificer_member['upgrades'] and
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
                    if best_crew_id in self.tools_used_this_heist:
                        print(f"  > {crew_member['name']} already used their tool this heist.")
                    else:
                        if effect.get('type') == 'bonus' and effect.get('skill') == event['check']:
                            tool_bonus = effect['value']
                            self.tools_used_this_heist.add(best_crew_id)
                            print(f"  > {crew_member['name']} uses {tool['name']} for a +{tool_bonus} bonus.")
                        elif effect.get('type') == 'difficulty_reduction':
                            condition = effect['condition'].replace('-', ' ')
                            if condition in event['description'].lower():
                                difficulty -= effect['value'] # Modify difficulty directly
                                self.tools_used_this_heist.add(best_crew_id)
                                print(f"  > {crew_member['name']} uses {tool['name']} to lower the difficulty by {effect['value']}.")
                        elif effect.get('type') == 'bypass' and effect.get('check') == event['check']:
                            bypass_check = True
                            self.city_agent.increase_notoriety(effect['notoriety'])
                            self.tools_used_this_heist.add(best_crew_id)
                            print(f"  > {crew_member['name']} uses {tool['name']} to bypass the check, gaining {effect['notoriety']} notoriety!")
                        elif effect.get('type') == 'special' and effect.get('id') == 'alchemy_craft':
                            use_kit = input(f"  > Use Alchemy Kit to grant a +{effect['value']} bonus to this {event['check']} check? [Y/N]: ").upper()
                            if use_kit == 'Y':
                                tool_bonus = effect['value']
                                self.tools_used_this_heist.add(best_crew_id)
                                print(f"  > {crew_member['name']} benefits from a potent elixir, gaining a +{tool_bonus} bonus.")

            # --- Ability Check (from Level-Up Upgrades) ---
            auto_succeed = False
            if (event['check'] == 'stealth' and
                'Shadowstep: Once per heist, auto-succeed a stealth check' in crew_member['upgrades'] and
                'shadowstep' not in self.abilities_used_this_heist):
                use_ability = input(f"  > Use {crew_member['name']}'s 'Shadowstep' to automatically succeed? [Y/N]: ").upper()
                if use_ability == 'Y':
                    print(f"  > [Shadowstep] {crew_member['name']} vanishes and reappears past the obstacle!")
                    auto_succeed = True
                    self.abilities_used_this_heist.add('shadowstep')


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
                        'Chronoward: Once per heist, rewind one failed check as if it never happened' in mage_member['upgrades'] and
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
            if result == self.crew_agent.SUCCESS:
                event_outcomes['success'] += 1
                success_msg = event.get('success', "The crew succeeded.")
                print(f"  > Success: {success_msg}")

                # --- Arcane Reservoir Store ---
                mage_member = self.crew_agent.get_crew_member('mage_1')
                if ('mage_1' in crew_ids and
                        'Arcane Reservoir: Store one success to spend later' in mage_member['upgrades'] and
                        not self.arcane_reservoir_stored and # Can't store if one is already held
                        'arcane_reservoir_store' not in self.abilities_used_this_heist): # Can only store once
                    store_success = input("  > Store this success in Lyra's Arcane Reservoir for later use? [Y/N]: ").upper()
                    if store_success == 'Y':
                        self.arcane_reservoir_stored = True
                        self.abilities_used_this_heist.add('arcane_reservoir_store')
                        print("  > [Arcane Reservoir] The moment of success is captured and stored.")
            elif result == self.crew_agent.PARTIAL:
                event_outcomes['partial'] += 1
                partial_msg = event.get('partial_success', "The crew managed, but with a complication.")
                print(f"  > Partial Success: {partial_msg}")
                # Simple parsing for mechanical effects
                if "notoriety +" in partial_msg:
                    match = re.search(r"notoriety \+(\d+)", partial_msg)
                    if match:
                        self.city_agent.increase_notoriety(int(match.group(1)))
                
                # Check for temporary stat penalties
                match = re.search(r"\((\w+)\s*–(\d+)\s*(\w+)", partial_msg)
                if match:
                    role_to_debuff, value_str, skill_to_debuff = match.groups()
                    debuff_value = -int(value_str)
                    target_crew_id = None
                    # Find the crew member with the specified role
                    for crew_id in crew_ids:
                        member = self.crew_agent.get_crew_member(crew_id)
                        if member and member['role'].lower() == role_to_debuff.lower():
                            target_crew_id = crew_id
                            break
                    
                    if target_crew_id:
                        if target_crew_id not in self.temporary_effects:
                            self.temporary_effects[target_crew_id] = {}
                        # Apply the debuff
                        self.temporary_effects[target_crew_id][skill_to_debuff] = self.temporary_effects[target_crew_id].get(skill_to_debuff, 0) + debuff_value
                        print(f"  > [Effect Applied!] {self.crew_agent.get_crew_member(target_crew_id)['name']}'s {skill_to_debuff} is temporarily reduced by {value_str}!")

                matches = re.finditer(r"(fear|respect)\s*([+\-–])\s*(\d+)", partial_msg)
                for match in matches:
                    rep_type, sign, value_str = match.groups()
                    value = int(value_str)
                    if sign in ['-', '–']: value = -value
                    self.city_agent.update_reputation(rep_type, value)
            else: # Failure
                event_outcomes['failure'] += 1
                failure_msg = event.get('failure', "The crew failed.")
                print(f"  > Failure: {failure_msg}")
                if "Notoriety increases" in failure_msg:
                    self.city_agent.increase_notoriety()
                if "injured" in failure_msg:
                    print(f"  > {crew_member['name']} is injured and cannot join the next heist!")
                    crew_member['status'] = "injured"

        # --- Heist Resolution ---
        leveled_up_crew = []
        heist_successful = event_outcomes['failure'] == 0

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

    def increase_notoriety(self, amount=1):
        self.notoriety += amount
        print(f"[City Update] Notoriety increased to {self.notoriety}")

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

    def save_game(self, filename="save_game.json"):
        save_data = {
            "notoriety": self.city_agent.notoriety,
            "loot": self.city_agent.loot,
            "crew_members": self.crew_agent.crew_members,
            "reputation": self.city_agent.reputation
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
            self.crew_agent.crew_members = save_data['crew_members']
            # To support older save files, we use .get()
            self.city_agent.reputation = save_data.get('reputation', {"fear": 0, "respect": 0})
            print(f"[Game loaded from {filename}.]")
            # Re-initialize agents that depend on loaded data if necessary
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
            # Check for game-state-altering special events
            if self.city_agent.notoriety >= 12: # Threshold from game_data.json
                print("\n[!!!] The Brasshaven Watch has cornered you!")
                # Here you would trigger a special 'escape' heist or event
                # For now, we can just print a message and reset notoriety as a placeholder
                print("You narrowly escape, but have to lay low. Your notoriety is reduced.")
                self.city_agent.notoriety = 5 # Reset to a lower value

            print("\n--- Main Menu ---")
            print(f"Notoriety: {self.city_agent.notoriety} | Reputation: Fear {self.city_agent.reputation['fear']}, Respect {self.city_agent.reputation['respect']}")

            current_loot = "None"
            if self.city_agent.loot:
                current_loot = ', '.join([item['item'] for item in self.city_agent.loot])
            print(f"Loot: {current_loot}")

            print("\n[P]lan Heist")
            print("[C]rew Roster") # A good place to see crew details
            print("[M]arket / Hideout") # The new loot sink
            print("[S]ave Game")
            print("[E]xit Game")
            
            action = input("> ").upper()

            if action == 'P':
                self.plan_and_execute_heist()
            elif action == 'S':
                self.save_game()
            elif action == 'M':
                self.show_market_menu() # A new method you would need to create
            elif action == 'E':
                print("\nYou melt back into the shadows of Brasshaven...")
                break
            else:
                print("Invalid choice. Please try again.")

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
                print(f"  [{i+1}] {upgrade}")

            # Get player choice
            choice = -1
            while choice < 1 or choice > len(available_upgrades):
                try:
                    choice_str = input(f"Enter number (1-{len(available_upgrades)}): ")
                    choice = int(choice_str)
                except ValueError:
                    print("Invalid input.")

            selected_upgrade = available_upgrades[choice - 1]
            member['upgrades'].append(selected_upgrade)
            print(f"{member['name']} has learned: '{selected_upgrade}'!")

            # Apply simple stat boosts immediately
            match = re.search(r"Increase (\w+) by \+(\d+)", selected_upgrade)
            if match:
                skill, value = match.groups()
                member['skills'][skill.lower()] += int(value)
                print(f"[Skill Increased] {member['name']}'s {skill.lower()} is now {member['skills'][skill.lower()]}.")

    def show_market_menu(self):
        """Handles the logic for spending loot and managing the hideout."""
        print("\n--- The Black Market ---")
        print("Feature coming soon! Here you'll be able to spend your loot.")
        print(f"Current Treasury: {sum(item['value'] for item in self.city_agent.loot)} coin.")
        input("Press Enter to return to the main menu...")
    
    def plan_and_execute_heist(self):
        # 1. Choose Heist
        print("\nAvailable Heists:")
        for heist_id, heist in self.heist_agent.heists.items():
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
            print(f"  [{crew_id}] {crew['name']} ({crew['role']}) - Lvl: {level} ({xp}/{next_lvl_xp} XP) - Skills: {crew['skills']}")

        chosen_crew_ids_str = input("Select your crew (e.g., rogue_1,mage_1): ")
        chosen_crew_ids = [c.strip() for c in chosen_crew_ids_str.split(',')]

        for crew_id in chosen_crew_ids:
            member = self.crew_agent.get_crew_member(crew_id)
            if member and member.get('status') == 'injured':
                print(f"[Invalid Crew] {member['name']} is injured and cannot join the heist. Please plan again.")
                return # Abort the heist planning

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
        print("\nAvailable Tools:")
        for tool_id, tool in self.tool_agent.tools.items():
            print(f"  [{tool_id}] {tool['name']} (Usable by: {', '.join(tool['usable_by'])})")

        for crew_id in chosen_crew_ids:
            crew_member = self.crew_agent.get_crew_member(crew_id)
            if not crew_member: continue

            tool_id = input(f"Assign a tool to {crew_member['name']} (or press Enter to skip): ")
            if tool_id and tool_id in self.tool_agent.tools and self.tool_agent.validate_tool_usage(tool_id, crew_member['role']):
                tool_assignments[crew_id] = tool_id
            elif tool_id:
                print("Invalid or unusable tool. Skipping assignment.")

        # 4. Run Heist
        leveled_up_crew = self.heist_agent.run_heist(chosen_heist_id, chosen_crew_ids, tool_assignments)
        if leveled_up_crew:
            self._handle_level_ups(leveled_up_crew)


if __name__ == "__main__":
    game = GameManager()
    game.start_game()
