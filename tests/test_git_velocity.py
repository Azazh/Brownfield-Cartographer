import unittest
from src.analyzers.git_velocity import extract_git_velocity, get_high_velocity_core


class TestGitVelocity(unittest.TestCase):
    def test_extract_git_velocity_empty(self):
        try:
            self.assertEqual(extract_git_velocity([], 30), {})
        except Exception as e:
            import traceback
            print("[TestGitVelocity] Exception in test_extract_git_velocity_empty:")
            traceback.print_exc()
            raise

    def test_get_high_velocity_core_empty(self):
        try:
            self.assertEqual(get_high_velocity_core({}, 0.2), [])
        except Exception as e:
            import traceback
            print("[TestGitVelocity] Exception in test_get_high_velocity_core_empty:")
            traceback.print_exc()
            raise

if __name__ == "__main__":
    unittest.main()
