import unittest

from runtime.task import summarize_objective, validate_request


class TaskOperationTests(unittest.TestCase):
    def test_known_digest_and_word_count(self):
        self.assertEqual(summarize_objective("hello world"), {
            "objective": "hello world",
            "word_count": 2,
            "sha256": "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
        })

    def test_preserves_objective_and_handles_unicode_whitespace(self):
        objective = "  Olá\n mundo\t"
        result = summarize_objective(objective)
        self.assertEqual(result["objective"], objective)
        self.assertEqual(result["word_count"], 2)
        self.assertEqual(validate_request({"objective": objective}), (objective, 30))

    def test_rejects_bad_input_before_work(self):
        for request in (None, [], {}, {"objective": " "}, {"objective": 1}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                validate_request(request)
        for delay in (-1, 301, True, 1.5, "30", None):
            with self.subTest(delay=delay), self.assertRaises(ValueError):
                validate_request({"objective": "test", "delay_seconds": delay})

    def test_delay_boundaries(self):
        for delay in (0, 300):
            self.assertEqual(validate_request({
                "objective": "test", "delay_seconds": delay,
            }), ("test", delay))


if __name__ == "__main__":
    unittest.main()
