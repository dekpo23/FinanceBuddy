import unittest
import os
import sys
import json

# Add root dir to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.onboarding import get_onboarding_schema

class TestOnboardingSchema(unittest.TestCase):
    
    def test_get_schema(self):
        schema = get_onboarding_schema()
        self.assertIn("questions", schema)
        self.assertTrue(len(schema.get("questions", [])) > 0)
        
    def test_get_questions(self):
        from agents.onboarding import get_onboarding_questions
        questions = get_onboarding_questions()
        self.assertTrue(isinstance(questions, list))
        self.assertTrue(len(questions) > 0)

if __name__ == '__main__':
    unittest.main()
