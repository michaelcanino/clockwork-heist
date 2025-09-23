import unittest
from unittest.mock import patch, MagicMock
import main

class TestGameAgents(unittest.TestCase):

    def setUp(self):
        """Set up test data and agents before each test."""
        self.game_data = {
            "crew_members": [
                {
                    "id": "rogue_1", "name": "Silas", "role": "Rogue",
                    "skills": {"stealth": 5, "lockpicking": 4, "combat": 2, "magic": 0},
                    "xp": 0, "level": 1, "upgrades": []
                },
                {
                    "id": "mage_1", "name": "Lyra", "role": "Mage",
                    "skills": {"stealth": 2, "lockpicking": 0, "combat": 3, "magic": 5},
                    "xp": 0, "level": 1, "upgrades": []
                }
            ],
            "tools": [
                {"id": "tool_lockpick", "name": "Lockpicks", "effect": "Boosts lockpicking by +2", "usable_by": ["Rogue"]},
                {"id": "tool_gadget", "name": "Smoke Bomb", "effect": "Boosts stealth by +2", "usable_by": ["Rogue", "Artificer"]}
            ],
            "heists": [
                {
                    "id": "heist_1", "name": "The Noble’s Manor", "events": [
                        {"id": "event_guard", "description": "A guard patrol", "check": "stealth", "difficulty": 3, "success": "s", "failure": "f"},
                        {"id": "event_ward", "description": "A magic ward", "check": "magic", "difficulty": 4, "success": "s", "failure": "f"}
                    ],
                    "potential_loot": [{"item": "Dagger", "value": 100}]
                }
            ],
            "player": {"starting_notoriety": 0, "starting_loot": [], "reputation": {"fear": 0, "respect": 0}},
            "progression": {"xp_thresholds": [0, 10, 25, 50]},
            "special_events": []
        }
        self.crew_agent = main.CrewAgent(self.game_data['crew_members'], self.game_data['progression'])
        self.tool_agent = main.ToolAgent(self.game_data['tools'])
        self.city_agent = main.CityAgent(self.game_data['player'])
        self.heist_agent = main.HeistAgent(
            self.game_data['heists'],
            self.game_data.get('random_events', []),
            self.game_data['special_events'],
            self.crew_agent,
            self.tool_agent,
            self.city_agent
        )

    # --- CrewAgent Tests ---
    @patch('random.randint', return_value=5)
    def test_perform_skill_check_success(self, mock_randint):
        """Test a successful skill check."""
        result = self.crew_agent.perform_skill_check('rogue_1', 'stealth', 10)
        self.assertEqual(result, main.CrewAgent.SUCCESS)

    @patch('random.randint', return_value=2)
    def test_perform_skill_check_failure(self, mock_randint):
        """Test a failed skill check."""
        result = self.crew_agent.perform_skill_check('rogue_1', 'stealth', 10)
        self.assertEqual(result, main.CrewAgent.FAILURE)

    # --- ToolAgent Tests (Updated for Phase 2) ---
    def test_get_tool_effect_bonus(self):
        """Test getting a structured bonus effect."""
        effect = self.tool_agent.get_tool_effect('tool_lockpick', 'Rogue')
        self.assertEqual(effect, {'type': 'bonus', 'skill': 'lockpicking', 'value': 2})

    def test_get_tool_effect_invalid_role(self):
        """Test getting no effect for an invalid role."""
        effect = self.tool_agent.get_tool_effect('tool_lockpick', 'Mage')
        self.assertEqual(effect, {})

    def test_validate_tool_usage(self):
        """Test tool usage validation."""
        self.assertTrue(self.tool_agent.validate_tool_usage('tool_gadget', 'Rogue'))
        self.assertFalse(self.tool_agent.validate_tool_usage('tool_lockpick', 'Mage'))

    # --- CityAgent Tests ---
    def test_increase_notoriety(self):
        """Test that notoriety increases correctly."""
        initial_notoriety = self.city_agent.notoriety
        self.city_agent.increase_notoriety(2)
        self.assertEqual(self.city_agent.notoriety, initial_notoriety + 2)

    def test_add_loot(self):
        """Test that loot is added correctly."""
        initial_loot_count = len(self.city_agent.loot)
        new_loot = {"item": "Gold Watch", "value": 50}
        self.city_agent.add_loot(new_loot)
        self.assertEqual(len(self.city_agent.loot), initial_loot_count + 1)
        self.assertIn(new_loot, self.city_agent.loot)

    # --- HeistAgent Integration Tests (Updated for Phase 2) ---
    @patch('builtins.input', return_value='N') # Mock user input for abilities
    @patch('main.CrewAgent.perform_skill_check', return_value=main.CrewAgent.SUCCESS)
    def test_run_heist_success(self, mock_skill_check, mock_input):
        """Test a fully successful heist."""
        crew_ids = ['rogue_1', 'mage_1']
        tool_assignments = {'rogue_1': 'tool_gadget'}
        initial_loot_count = len(self.city_agent.loot)

        heist_agent = main.HeistAgent(
            self.game_data['heists'],
            self.game_data.get('random_events', []),
            self.game_data['special_events'],
            self.crew_agent,
            self.tool_agent,
            self.city_agent
        )
        heist_agent.run_heist('heist_1', crew_ids, tool_assignments)

        self.assertGreater(len(self.city_agent.loot), initial_loot_count)
        self.assertEqual(self.city_agent.loot[0]['item'], 'Dagger')

    @patch('builtins.input', return_value='N') # Mock user input for abilities
    @patch('main.CrewAgent.perform_skill_check', side_effect=[main.CrewAgent.SUCCESS, main.CrewAgent.FAILURE])
    def test_run_heist_failure(self, mock_skill_check, mock_input):
        """Test a heist that fails on the second event."""
        crew_ids = ['rogue_1', 'mage_1']
        tool_assignments = {}
        initial_loot_count = len(self.city_agent.loot)

        heist_agent = main.HeistAgent(
            self.game_data['heists'],
            self.game_data.get('random_events', []),
            self.game_data['special_events'],
            self.crew_agent,
            self.tool_agent,
            self.city_agent
        )
        heist_agent.run_heist('heist_1', crew_ids, tool_assignments)

        self.assertEqual(len(self.city_agent.loot), initial_loot_count)


if __name__ == '__main__':
    unittest.main()
