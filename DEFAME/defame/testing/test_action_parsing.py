import unittest
from unittest.mock import patch

from defame.prompts.prompts import extract_actions
from defame.tools.search.common import WebSearch, ImageSearch


class ActionParsingTests(unittest.TestCase):
    actions = ('web_search("Sahara Desert snow coverage 2023")\n'
               'image_search("Sahara Desert snow 2023")')

    def assert_actions(self, answer, expected=None):
        with patch('defame.prompts.prompts.logger.warning') as warning:
            result = extract_actions(answer)
        warning.assert_not_called()
        self.assertEqual([str(a) for a in result], expected or self.actions.splitlines())
        return result

    def test_language_tags(self):
        for tag in ('text', 'markdown', 'python', 'json', 'plaintext', 'c++'):
            with self.subTest(tag=tag):
                result = self.assert_actions(f'```{tag}\n{self.actions}\n```')
                self.assertIsInstance(result[0], WebSearch)
                self.assertIsInstance(result[1], ImageSearch)

    def test_plain_inline_open_and_crlf_blocks(self):
        for answer in (f'```\n{self.actions}\n```',
                       f'```text\n{self.actions}',
                       '```text\r\n  web_search("Sahara Desert snow coverage 2023")\r\n\r\n'
                       '  image_search("Sahara Desert snow 2023")\r\n```'):
            with self.subTest(answer=answer):
                self.assert_actions(answer)
        self.assert_actions('```web_search("Sahara snow")```', ['web_search("Sahara snow")'])

    def test_query_contents_are_preserved(self):
        action = 'web_search("markdown text documentation")'
        self.assert_actions(f'```markdown\n{action}\n```', [action])

    def test_last_block_and_unfenced_fallback(self):
        self.assert_actions(f'```python\nprint("example")\n```\n```text\n{self.actions}\n```')
        self.assert_actions('Search plan:\n' + self.actions)

    def test_invalid_actions_still_warn(self):
        with patch('defame.prompts.prompts.logger.warning') as warning:
            result = extract_actions('```text\nunknown_action("query")\n```')
        self.assertEqual(result, [])
        self.assertEqual(warning.call_count, 1)
        self.assertIn('unknown_action', warning.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
