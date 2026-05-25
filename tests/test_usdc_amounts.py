import unittest

from loaf_sizzler.contract_client import parse_usdc_amount


class USDCAmountTest(unittest.TestCase):
    def test_integer_values_are_raw_units(self):
        self.assertEqual(parse_usdc_amount(1), 1)
        self.assertEqual(parse_usdc_amount("2000000"), 2000000)

    def test_decimal_values_are_converted_to_raw_units(self):
        self.assertEqual(parse_usdc_amount("0.000001"), 1)
        self.assertEqual(parse_usdc_amount("0.000002"), 2)
        self.assertEqual(parse_usdc_amount("1.25"), 1250000)

    def test_sub_unit_values_are_rejected_instead_of_rounded_to_zero(self):
        with self.assertRaisesRegex(ValueError, "minimum non-zero"):
            parse_usdc_amount("0.0000002")

        with self.assertRaisesRegex(ValueError, "minimum non-zero"):
            parse_usdc_amount("0.000000012")

    def test_zero_and_negative_values_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "greater than 0"):
            parse_usdc_amount("0")

        with self.assertRaisesRegex(ValueError, "greater than 0"):
            parse_usdc_amount("-1")


if __name__ == "__main__":
    unittest.main()
