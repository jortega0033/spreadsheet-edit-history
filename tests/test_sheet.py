import unittest

from sheet_history import sheet as sh


class CellValidationTests(unittest.TestCase):
    def test_valid_ids_accepted(self):
        grid = sh.canonicalize_cells({"A1": "x", "F8": "y"})
        self.assertEqual(grid, {"A1": "x", "F8": "y"})

    def test_invalid_ids_rejected(self):
        for bad in ("G1", "A0", "A9", "a1", "AA1", "A10", " A1", "A1\n", "", "1A"):
            with self.subTest(bad=bad):
                with self.assertRaises(sh.ValidationError):
                    sh.canonicalize_cells({bad: "x"})

    def test_cells_must_be_object(self):
        for bad in (None, [], "A1", 3):
            with self.subTest(bad=bad):
                with self.assertRaises(sh.ValidationError):
                    sh.canonicalize_cells(bad)

    def test_values_must_be_strings(self):
        for bad in (3, None, True, ["x"], {"a": 1}):
            with self.subTest(bad=bad):
                with self.assertRaises(sh.ValidationError):
                    sh.canonicalize_cells({"A1": bad})

    def test_length_cap_counts_code_points(self):
        sh.canonicalize_cells({"A1": "a" * 200})
        sh.canonicalize_cells({"A1": "\U0001F600" * 200})
        with self.assertRaises(sh.ValidationError):
            sh.canonicalize_cells({"A1": "a" * 201})
        with self.assertRaises(sh.ValidationError):
            sh.canonicalize_cells({"A1": "\U0001F600" * 201})

    def test_control_chars_and_surrogates_rejected(self):
        for bad in ("\x00", "a\nb", "a\tb", "\x1f", "\x7f", "\r", "\ud800", "x\udfffy"):
            with self.subTest(bad=bad):
                with self.assertRaises(sh.ValidationError):
                    sh.canonicalize_cells({"A1": bad})

    def test_text_stored_exactly_without_trim(self):
        grid = sh.canonicalize_cells({"A1": "  a  ", "B1": " "})
        self.assertEqual(grid, {"A1": "  a  ", "B1": " "})

    def test_title_rules(self):
        self.assertEqual(sh.validate_title("x"), "x")
        sh.validate_title("t" * 80)
        for bad in ("", "t" * 81, "a\nb", "\x00", 5, None, "\ud800"):
            with self.subTest(bad=bad):
                with self.assertRaises(sh.ValidationError):
                    sh.validate_title(bad)


class CanonicalTests(unittest.TestCase):
    def test_empty_omitted_and_sorted_by_row_then_column(self):
        grid = sh.canonicalize_cells({"A2": "x", "F1": "y", "A1": "z", "B1": ""})
        self.assertEqual(list(grid), ["A1", "F1", "A2"])
        self.assertEqual(sh.dumps_grid(grid), '{"A1":"z","F1":"y","A2":"x"}')

    def test_empty_grid(self):
        self.assertEqual(sh.dumps_grid(sh.canonicalize_cells({})), "{}")

    def test_utf8_round_trip_not_escaped(self):
        text = "héllo ✓ 日本"
        dumped = sh.dumps_grid(sh.canonicalize_cells({"A1": text}))
        self.assertIn(text, dumped)
        self.assertEqual(sh.loads_grid(dumped), {"A1": text})

    def test_loads_rejects_corrupt(self):
        for bad in ("not json", "[]", '{"Z9":"x"}'):
            with self.subTest(bad=bad):
                with self.assertRaises(sh.ValidationError):
                    sh.loads_grid(bad)


class FormulaTests(unittest.TestCase):
    def calc(self, cells):
        return sh.compute(sh.canonicalize_cells(cells))

    def test_basic_sum(self):
        self.assertEqual(self.calc({"A1": "3", "B1": "4", "C1": "=A1+B1"}), {"C1": "7"})

    def test_decimal_normalization(self):
        cases = [
            ("0.1", "0.2", "0.3"),
            ("-5", "2.5", "-2.5"),
            ("1.50", "1.50", "3"),
            ("-0", "0", "0"),
            ("-1", "1", "0"),
            ("007", "3", "10"),
            ("100", "200", "300"),
        ]
        for a, b, want in cases:
            with self.subTest(a=a, b=b):
                self.assertEqual(self.calc({"A1": a, "B1": b, "C1": "=A1+B1"})["C1"], want)

    def test_large_numbers_exact(self):
        out = self.calc({"A1": "9" * 200, "B1": "1", "C1": "=A1+B1"})
        self.assertEqual(out["C1"], "1" + "0" * 200)

    def test_empty_operands_are_zero(self):
        self.assertEqual(self.calc({"A1": "5", "C1": "=A1+B1"}), {"C1": "5"})
        self.assertEqual(self.calc({"C1": "=A1+B1"}), {"C1": "0"})

    def test_text_operand_is_value_error(self):
        self.assertEqual(self.calc({"A1": "abc", "B1": "1", "C1": "=A1+B1"})["C1"], "#VALUE!")
        for text in ("+1", "-x", "@1", "1e5", ".5", "5.", "=5", " 5"):
            with self.subTest(text=text):
                out = self.calc({"A1": text, "B1": "1", "C1": "=A1+B1"})
                self.assertEqual(out["C1"], "#VALUE!")

    def test_nested_and_self_reference(self):
        out = self.calc({"A1": "=B1+B1", "C1": "=A1+A1"})
        self.assertEqual(out, {"A1": "0", "C1": "#NESTED"})
        self.assertEqual(self.calc({"A1": "=A1+A1"}), {"A1": "#NESTED"})

    def test_non_formulas_are_literal_and_not_computed(self):
        for text in ("=A1", "= A1+B1", "=A1+B1+C1", "=a1+b1", "=A1+B1 ", "=SUM(A1)",
                     "=1+2", "=A1-B1", "=A9+B1", "+1+2", "-A1+B1", "@A1+B1", "="):
            with self.subTest(text=text):
                self.assertEqual(self.calc({"D4": text, "A1": "1", "B1": "2"}), {})

    def test_literal_leading_chars_preserved_in_grid(self):
        cells = {"A1": "=1+2", "B1": "+x", "C1": "-y", "D1": "@z"}
        self.assertEqual(sh.canonicalize_cells(cells), cells)

    def test_formula_operand_that_is_literal_equals_text(self):
        out = self.calc({"A1": "=oops", "C1": "=A1+B1"})
        self.assertEqual(out, {"C1": "#VALUE!"})


if __name__ == "__main__":
    unittest.main()
