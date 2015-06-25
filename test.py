import time
import unittest
from util import CappedCache


class TestCappedCache(unittest.TestCase):

    def test_max_size(self):

        cc = CappedCache(max_size=5)

        cc['a'] = 'x'
        cc['b'] = 'x'
        cc['c'] = 'x'
        cc['d'] = 'x'
        cc['e'] = 'x'
        self.assertEqual(len(cc), 5)

        cc['e'] = 'x'
        self.assertEqual(len(cc), 5)
        self.assertTrue('e' in cc)

        cc['f'] = 'x'
        self.assertEqual(len(cc), 5)
        self.assertTrue('f' in cc)

    def test_timeout(self):

        cc = CappedCache()
        cc.set('a', 'x', timeout=1)

        self.assertTrue('a' in cc)
        self.assertEqual(cc['a'], 'x')

        time.sleep(2)

        self.assertFalse('a' in cc)
        self.assertIsNone(cc['a'])





if __name__ == '__main__':
    unittest.main()
