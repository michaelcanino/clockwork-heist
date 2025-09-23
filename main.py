import json
import random
import re

class CrewAgent:
    def __init__(self, crew_data):
        self.crew_members = {c['id']: c for c in crew_data}

    def get_crew_member(self, crew_id):
        return self.crew_members.get(crew_id)

    def perform_skill_check(self, crew_id, skill, difficulty):
        crew_member = self.get_crew_member(crew_id)
        if not crew_member:
            return False, "Crew member not found."

        skill_value = crew_member['skills'].get(skill, 0)
        roll = random.randint(1, 10)
        total_skill = skill_value + roll

        print(f"  > {crew_member['name']} attempts {skill} check (Difficulty: {difficulty})")
        print(f"  > Skill: {skill_value} + Roll: {roll} = Total: {total_skill}")

        return total_skill >= difficulty

class ToolAgent:
    def __init__(self, tool_data):
        self.tools = {t['id']: t for t in tool_data}

    def get_tool_effect(self, tool_id, crew_role):
        tool = self.tools.get(tool_id)
        if not (tool and crew_role in tool['usable_by']):
            return {}

        effect_str = tool['effect']

        # "Boosts <skill> by +<number>"
        match = re.search(r"Boosts (\w+) by \+(\d+)", effect_str)
        if match:
            return {'type': 'bonus', 'skill': match.group(1).lower(), 'value': int(match.group(2))}

        # "Lowers difficulty of <condition> events by <number>"
        match = re.search(r"Lowers difficulty of ([\w\s-]+) events by (\d+)", effect_str)
        if match:
            return {'type': 'difficulty_reduction', 'condition': match.group(1).strip(), 'value': int(match.group(2))}

        # "Breaks through vaults (lockpicking bypass) but increases notoriety by +<number>"
        match = re.search(r"\((\w+) bypass\) but increases notoriety by \+(\d+)", effect_str)
        if match:
            return {'type': 'bypass', 'check': match.group(1), 'notoriety': int(match.group(2))}

        # Alchemy kit - placeholder for now
        if "Allows crafting potions" in effect_str:
            return {'type': 'special', 'id': 'alchemy_craft'}

        return {}

    def validate_tool_usage(self, tool_id, crew_role):
        tool = self.tools.get(tool_id)
        return tool and crew_role in tool['usable_by']

class HeistAgent:
    def __init__(self, heist_data, random_events_data, crew_agent, tool_agent, city_agent):
        self.heists = {h['id']: h for h in heist_data}
        self.random_events = random_events_data
        self.crew_agent = crew_agent
        self.tool_agent = tool_agent
        self.city_agent = city_agent

    def run_heist(self, heist_id, crew_ids, tool_assignments):
        heist = self.heists.get(heist_id)
        if not heist:
            print("Heist not found.")
            return

        # --- Initialize Heist State ---
        print(f"\n--- Starting Heist: {heist['name']} ---")
        heist_successful = True
        total_loot = []
        self.abilities_used_this_heist = set()
        self.double_loot_active = False

        # --- Event Generation ---
        events_to_run = list(heist['events'])

        # Scout Ability Check for Random Events
        scout_present = 'scout_1' in crew_ids
        if self.random_events and random.randint(1, 4) == 1:
            random_event = random.choice(self.random_events).copy()
            random_event['description'] = f"[Random Event] {random_event['description']}"
            random_event.setdefault('success', "The crew handled the unexpected situation.")
            random_event.setdefault('failure', "The event causes a complication. Notoriety increases.")

            if scout_present and 'scout_1' not in self.abilities_used_this_heist:
                print(f"\n[Scout's Forewarning!] Finn Ashwhistle spots trouble ahead.")
                print(f"  > Upcoming Event: {random_event['description']}")
                self.abilities_used_this_heist.add('scout_1')
            else:
                print(f"[A random event occurs during the heist!]")

            insert_pos = random.randint(0, len(events_to_run))
            events_to_run.insert(insert_pos, random_event)

        # --- Main Event Loop ---
        for event in events_to_run:
            if not heist_successful:
                print("\nAn earlier failure has compromised the heist. Aborting.")
                break

            print(f"\n* Event: {event['description']}")

            # Alchemist Ability Check
            alchemist_bonus = 0
            alchemist_present = 'alchemist_1' in crew_ids
            if alchemist_present and 'alchemist_1' not in self.abilities_used_this_heist:
                use_ability = input(f"  > Use Alchemist's 'Shielding Elixir' for a +1 bonus on this event? [Y/N]: ").upper()
                if use_ability == 'Y':
                    alchemist_bonus = 1
                    self.abilities_used_this_heist.add('alchemist_1')
                    print("  > [Alchemist's Elixir] The crew feels invigorated by the potion!")

            # Find best crew member
            best_crew_id = None
            best_skill = -1
            for crew_id in crew_ids:
                member = self.crew_agent.get_crew_member(crew_id)
                if member and member['skills'].get(event['check'], 0) > best_skill:
                    best_skill = member['skills'].get(event['check'], 0)
                    best_crew_id = crew_id

            if not best_crew_id:
                print("No suitable crew member for this event.")
                heist_successful = False
                continue

            difficulty = event['difficulty'] - alchemist_bonus
            crew_member = self.crew_agent.get_crew_member(best_crew_id)

            # Tool Effects
            bypass_check = False
            tool_id = tool_assignments.get(best_crew_id)
            if tool_id:
                effect = self.tool_agent.get_tool_effect(tool_id, crew_member['role'])
                if effect:
                    tool = self.tool_agent.tools[tool_id]
                    if effect.get('type') == 'bonus' and effect.get('skill') == event['check']:
                        difficulty -= effect['value']
                        print(f"  > {crew_member['name']} uses {tool['name']} for a +{effect['value']} bonus.")
                    elif effect.get('type') == 'difficulty_reduction':
                        condition = effect['condition'].replace('-', ' ')
                        if condition in event['description'].lower():
                             difficulty -= effect['value']
                             print(f"  > {crew_member['name']} uses {tool['name']} to lower the difficulty by {effect['value']}.")
                    elif effect.get('type') == 'bypass' and effect.get('check') == event['check']:
                        bypass_check = True
                        self.city_agent.increase_notoriety(effect['notoriety'])
                        print(f"  > {crew_member['name']} uses {tool['name']} to bypass the check, gaining {effect['notoriety']} notoriety!")

            # Perform Check
            success = False
            if bypass_check:
                success = True
            else:
                success = self.crew_agent.perform_skill_check(best_crew_id, event['check'], difficulty)

            # Gambler Ability Check
            if not success:
                gambler_present = 'gambler_1' in crew_ids
                if gambler_present and 'gambler_1' not in self.abilities_used_this_heist:
                    use_ability = input(f"  > A setback! Use Gambler's 'Double or Nothing' to reroll? [Y/N]: ").upper()
                    if use_ability == 'Y':
                        self.abilities_used_this_heist.add('gambler_1')
                        print("  > [Gambler's Wager] Cassian Vey is betting it all on a second chance!")

                        if self.crew_agent.perform_skill_check(best_crew_id, event['check'], difficulty):
                            print("  > Reroll Success! The gamble paid off spectacularly!")
                            success = True
                            self.double_loot_active = True
                        else:
                            print("  > Reroll Failure! The house always wins. Notoriety increases sharply.")
                            self.city_agent.increase_notoriety(2)

            # Resolve Outcome
            if success:
                success_msg = event.get('success', "The crew succeeded.")
                print(f"  > Success: {success_msg}")
            else:
                failure_msg = event.get('failure', "The crew failed.")
                print(f"  > Failure: {failure_msg}")
                if "Notoriety increases" in failure_msg:
                    self.city_agent.increase_notoriety()
                if "injured" in failure_msg:
                    print(f"  > {crew_member['name']} is injured!")
                heist_successful = False

        # --- Heist Resolution ---
        if heist_successful:
            print("\n--- Heist Successful! ---")
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

        print(f"Final Notoriety: {self.city_agent.notoriety}")
        print(f"Total Loot Acquired: {[item['item'] for item in total_loot]}")


class CityAgent:
    def __init__(self, player_data):
        self.notoriety = player_data['starting_notoriety']
        self.loot = list(player_data['starting_loot'])

    def increase_notoriety(self, amount=1):
        self.notoriety += amount
        print(f"[City Update] Notoriety increased to {self.notoriety}")

    def add_loot(self, item):
        self.loot.append(item)
        print(f"[City Update] Loot acquired: {item['item']} (Value: {item['value']})")

class GameManager:
    def __init__(self):
        with open('game_data.json', 'r', encoding='utf-8') as f:
            self.game_data = json.load(f)

        self.city_agent = CityAgent(self.game_data['player'])
        self.crew_agent = CrewAgent(self.game_data['crew_members'])
        self.tool_agent = ToolAgent(self.game_data['tools'])
        self.heist_agent = HeistAgent(
            self.game_data['heists'],
            self.game_data['random_events'],
            self.crew_agent,
            self.tool_agent,
            self.city_agent
        )

    def save_game(self, filename="save_game.json"):
        save_data = {
            "notoriety": self.city_agent.notoriety,
            "loot": self.city_agent.loot
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
            print(f"[Game loaded from {filename}.]")
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
            print("\n--- Main Menu ---")
            print(f"Notoriety: {self.city_agent.notoriety}")

            current_loot = "None"
            if self.city_agent.loot:
                current_loot = ', '.join([item['item'] for item in self.city_agent.loot])
            print(f"Loot: {current_loot}")

            print("\n[P]lan Heist")
            print("[S]ave Game")
            print("[E]xit Game")
            action = input("> ").upper()

            if action == 'P':
                self.plan_and_execute_heist()
            elif action == 'S':
                self.save_game()
            elif action == 'E':
                print("\nYou melt back into the shadows of Brasshaven...")
                break
            else:
                print("Invalid choice. Please try again.")

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
        for crew_id, crew in self.crew_agent.crew_members.items():
            print(f"  [{crew_id}] {crew['name']} ({crew['role']}) - Skills: {crew['skills']}")

        chosen_crew_ids_str = input("Select your crew (e.g., rogue_1,mage_1): ")
        chosen_crew_ids = [c.strip() for c in chosen_crew_ids_str.split(',')]

        valid_crew = all(self.crew_agent.get_crew_member(c_id) for c_id in chosen_crew_ids)
        if not valid_crew or not chosen_crew_ids:
            print("Invalid crew selection. Returning to Main Menu.")
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
        self.heist_agent.run_heist(chosen_heist_id, chosen_crew_ids, tool_assignments)


if __name__ == "__main__":
    game = GameManager()
    game.start_game()
