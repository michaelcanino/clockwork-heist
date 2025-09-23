import json
import random

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

    def get_tool_bonus(self, tool_id, crew_role):
        tool = self.tools.get(tool_id)
        if tool and crew_role in tool['usable_by']:
            # A simple implementation: extract bonus from effect string
            try:
                bonus = int(tool['effect'].split('+')[-1])
                return bonus
            except (ValueError, IndexError):
                return 0
        return 0

    def validate_tool_usage(self, tool_id, crew_role):
        tool = self.tools.get(tool_id)
        return tool and crew_role in tool['usable_by']

class HeistAgent:
    def __init__(self, heist_data, crew_agent, tool_agent, city_agent):
        self.heists = {h['id']: h for h in heist_data}
        self.crew_agent = crew_agent
        self.tool_agent = tool_agent
        self.city_agent = city_agent

    def run_heist(self, heist_id, crew_ids, tool_assignments):
        heist = self.heists.get(heist_id)
        if not heist:
            print("Heist not found.")
            return

        print(f"\n--- Starting Heist: {heist['name']} ---")
        heist_successful = True
        total_loot = []

        for event in heist['events']:
            print(f"\n* Event: {event['description']}")

            # Find the best crew member for the check
            best_crew_id = None
            best_skill = -1

            for crew_id in crew_ids:
                crew_member = self.crew_agent.get_crew_member(crew_id)
                if crew_member and crew_member['skills'].get(event['check'], 0) > best_skill:
                    best_skill = crew_member['skills'].get(event['check'], 0)
                    best_crew_id = crew_id

            if not best_crew_id:
                print("No suitable crew member for this event.")
                heist_successful = False
                break

            # Check for tool bonus
            difficulty = event['difficulty']
            crew_member = self.crew_agent.get_crew_member(best_crew_id)
            tool_id = tool_assignments.get(best_crew_id)
            if tool_id:
                bonus = self.tool_agent.get_tool_bonus(tool_id, crew_member['role'])
                if bonus > 0:
                    print(f"  > {crew_member['name']} uses {self.tool_agent.tools[tool_id]['name']} for a bonus.")
                    difficulty -= bonus


            success = self.crew_agent.perform_skill_check(best_crew_id, event['check'], difficulty)

            if success:
                print(f"  > Success: {event['success']}")
            else:
                print(f"  > Failure: {event['failure']}")
                if "Notoriety increases" in event['failure']:
                    self.city_agent.increase_notoriety()
                if "injured" in event['failure']:
                    # MVP: For now, just a message. A real game would track this.
                    print(f"  > {crew_member['name']} is injured!")
                heist_successful = False

        if heist_successful:
            print("\n--- Heist Successful! ---")
            for loot_item in heist['potential_loot']:
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
        with open('game_data.json', 'r') as f:
            self.game_data = json.load(f)

        self.city_agent = CityAgent(self.game_data['player'])
        self.crew_agent = CrewAgent(self.game_data['crew_members'])
        self.tool_agent = ToolAgent(self.game_data['tools'])
        self.heist_agent = HeistAgent(
            self.game_data['heists'],
            self.crew_agent,
            self.tool_agent,
            self.city_agent
        )

    def start_game(self):
        print("Welcome to The Clockwork Heist!")
        print("="*30)

        # Automated test run for MVP verification
        print("\n--- Automated Test Run ---")

        # 1. Choose Heist
        chosen_heist_id = "heist_1"
        print(f"\nChosen Heist: {self.heist_agent.heists[chosen_heist_id]['name']}")

        # 2. Select Crew
        chosen_crew_ids = ["rogue_1", "mage_1"]
        print("\nChosen Crew:")
        for crew_id in chosen_crew_ids:
            crew_member = self.crew_agent.get_crew_member(crew_id)
            print(f"  - {crew_member['name']} ({crew_member['role']})")

        # 3. Assign Tools
        tool_assignments = {
            "rogue_1": "tool_lockpick",
            "mage_1": "tool_rune"
        }
        print("\nTool Assignments:")
        for crew_id, tool_id in tool_assignments.items():
            crew_member = self.crew_agent.get_crew_member(crew_id)
            tool = self.tool_agent.tools[tool_id]
            print(f"  - {crew_member['name']} gets {tool['name']}")

        # 4. Run Heist
        self.heist_agent.run_heist(chosen_heist_id, chosen_crew_ids, tool_assignments)

        print("\n--- Game Over ---")


if __name__ == "__main__":
    game = GameManager()
    game.start_game()
