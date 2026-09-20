from pathlib import Path
import tempfile
import unittest
from runtime.kernel.procedure import ProcedureContext


class ProcedureTests(unittest.TestCase):
    def test_only_selected_task_gets_digest_bound_non_authoritative_instructions(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'procedure.md';path.write_text('Ask one material clarification.')
            provider=ProcedureContext(path,'fixture:procedure',frozenset({'selected'}))
            item=provider({'task_id':'selected','max_bytes':4096})[0]
            self.assertEqual(item['authority'],'derived')
            self.assertEqual(provider({'task_id':'unrelated','max_bytes':4096}),[])
            path.write_text('Updated guidance')
            self.assertNotEqual(item['revision'],provider({'task_id':'selected','max_bytes':4096})[0]['revision'])
            with self.assertRaises(ValueError):provider({'task_id':'selected','max_bytes':10})


if __name__=='__main__':unittest.main()
