from user_code import multiply
import unittest


def actual(a, b):
    return a * b


arr = [(7, 8), (9, 1), (3, 1)]


class RandomTest(unittest.TestCase):
    def test_multiply(self):
        for a, b in arr:
            with self.subTest(i=a):
                self.assertEqual(multiply(a, b), actual(a, b))


if __name__ == '__main__':
    unittest.main()
