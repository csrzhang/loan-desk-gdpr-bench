"""Offline migration checks. These do not produce benchmark predictions."""
import json
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from graph import build_graph
from regulatory import render_case, visible_lines
from run import AUDIT, HERE, FILES, VERSIONS, load, packet


class PortChecks(unittest.TestCase):
    def test_explicit_credentials_take_precedence_across_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'.env'
            path.write_text('ANTHROPIC_API_KEY=file-account\nLLM_MODEL=deepseek-flash\n')
            environment = {'PRIAGENT_ENV_FILE':str(path), 'DEEPSEEK_API_KEY':'shell-account',
                           'LLM_MODEL':'deepseek-v4-pro'}
            with patch.dict(os.environ, environment, clear=True):
                settings = runpy.run_path(str(HERE/'config.py'))
                self.assertEqual(settings['LLM_API_KEY'], 'file-account')
                self.assertEqual(settings['LLM_MODEL'], 'deepseek-v4-pro')
                self.assertEqual(settings['LLM_KEY_SOURCE'], 'PRIAGENT_ENV_FILE (ANTHROPIC_API_KEY)')
                path.write_text('')
                self.assertIsNone(runpy.run_path(str(HERE/'config.py'))['LLM_API_KEY'])
                del os.environ['PRIAGENT_ENV_FILE']
                self.assertEqual(runpy.run_path(str(HERE/'config.py'))['LLM_API_KEY'], 'shell-account')

    def test_public_inputs_on_all_five_snapshots(self):
        scope=load(AUDIT/'scope.json')
        rules=load(HERE/'requirements-by-rule.json')
        ids=set()
        for project in VERSIONS:
            for obligation in scope['obligations']:
                case=packet(project,obligation,scope,rules[obligation['obligation_id']])
                self.assertEqual(set(case),{'law','source','assumptions','rule','scenario','files','case_id'})
                self.assertEqual([f['path'] for f in case['files']],list(FILES))
                self.assertRegex(case['case_id'],r'^case-[a-f0-9]{16}$')
                for f in case['files']:
                    self.assertEqual(list(visible_lines(f).values()),(AUDIT/'projects'/project/f['path']).read_text().splitlines())
                self.assertIn('ARTIFACT app.py', render_case(case))
                ids.add(case['case_id'])
        self.assertEqual(len(ids),65)

    def test_independent_runtime_replays_real_provider_decision(self):
        run=HERE/'runs/flash-01'
        directory=run/'cases/base-GDPR01'
        scope=load(AUDIT/'scope.json')
        public=packet('base',scope['obligations'][0],scope,load(HERE/'requirements-by-rule.json')['GDPR01'])
        class Recorded:
            case=public
            def call(self,stage,schema,context):
                return schema.model_validate(load(directory/'stages'/(stage+'.json'))['output'])
        final=build_graph(Recorded()).invoke({})
        prediction=load(directory/'prediction.json')
        self.assertEqual(final['validation']['validation_status'],'VALID')
        self.assertEqual(final['answer']['status'],prediction['verdict'])
        self.assertEqual(final['answer']['detailed_explanation'],prediction['explanation'])
        for a,b in zip(final['answer']['evidence'],prediction['evidence'],strict=True):
            self.assertEqual((a['artifact'],a['start_line'],a['end_line'],a['quoted_text'],a['explanation']),
                             (b['path'],b['start_line'],b['end_line'],b['quote'],b['supports']))

if __name__=='__main__':
    unittest.main()
