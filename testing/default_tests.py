import unittest
from user_code import user_func


class CodeTest(unittest.TestCase):
    def test_1(self):
        self.assertEqual(user_func(), )


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
