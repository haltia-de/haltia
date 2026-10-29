#!/usr/bin/env python3
"""Exercise the real probe result/exit boundary without GTK or product imports."""
import ast,json,pathlib,tempfile,types,unittest
from unittest.mock import Mock
PROBE=pathlib.Path(__file__).with_name('gtk_probe.py')
class Completion(unittest.TestCase):
 def evaluate(self,rc,checks,appname='weather',phase='change'):
  tree=ast.parse(PROBE.read_text());start=next(i for i,node in enumerate(tree.body) if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and isinstance(node.value.func.value,ast.Name) and node.value.func.value.id=='GLib' and node.value.func.attr=='timeout_add_seconds')
  boundary=ast.Module(body=tree.body[start:],type_ignores=[])
  with tempfile.TemporaryDirectory(prefix='haltia-probe-exit-') as tmp:
   namespace=dict(GLib=types.SimpleNamespace(timeout_add_seconds=Mock()),tick=Mock(),app=types.SimpleNamespace(run=Mock(return_value=rc)),appname=appname,args=types.SimpleNamespace(phase=phase),out=pathlib.Path(tmp),results=[dict(check=name,status='pass') for name in checks],json=json,sys=__import__('sys'))
   try:exec(compile(boundary,str(PROBE),'exec'),namespace)
   except SystemExit as exc:return exc.code,namespace['results']
   self.fail('Probe did not return an explicit status')
 def test_early_application_failure_is_not_pass(self):self.assertNotEqual(self.evaluate(1,[])[0],0)
 def test_empty_successful_application_is_not_pass(self):self.assertNotEqual(self.evaluate(0,[])[0],0)
 def test_missing_last_stage_is_not_pass(self):self.assertNotEqual(self.evaluate(0,['home','settings','after-interaction','after-local-change'])[0],0)
 def test_application_error_after_all_stages_is_not_pass(self):self.assertNotEqual(self.evaluate(1,['home','settings','after-interaction','after-local-change','returned'])[0],0)
 def test_all_weather_stages_and_clean_exit_pass(self):self.assertEqual(self.evaluate(0,['home','settings','after-interaction','after-local-change','returned'])[0],0)
 def test_music_requires_ui_switch_check(self):self.assertNotEqual(self.evaluate(0,['home','settings','after-interaction','after-local-change','returned'],'music')[0],0)
 def test_paint_restart_requires_region_check(self):self.assertNotEqual(self.evaluate(0,['home','settings','after-interaction','after-local-change','returned','picture','painted'],'paint','restart')[0],0)
if __name__=='__main__':unittest.main(verbosity=2)
