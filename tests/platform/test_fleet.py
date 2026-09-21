"""Fleet credentials cannot cross stack/product identities or leak bootstrap."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('fleet_materializer',Path(__file__).resolve().parents[2]/'infra/grafana-cloud.py')
cloud=importlib.util.module_from_spec(spec);spec.loader.exec_module(cloud)
class FleetSecretTests(unittest.TestCase):
 def values(self):
  return dict(zip(cloud.FLEET_FIELDS,['https://fleet-management-prod-015.grafana.net','1838998','synthetic_fleet_test_credential_only']))
 def test_product_identity_and_endpoint_are_pinned(self):
  for field,bad in [(0,'https://fleet-management-prod-015.grafana.net.evil.invalid'),(0,'https://fleet-management-prod-015.grafana.net/v1/opamp'),(1,'3602220'),(1,'1796781'),(2,'x\nINJECT=yes'),(2,'$(id)')]:
   values=self.values();values[cloud.FLEET_FIELDS[field]]=bad
   with self.subTest(field=field,bad=bad),self.assertRaises(ValueError):cloud.validate_fleet(values)
 def test_unexpected_bootstrap_fields_rejected(self):
  values=self.values();values['BWS_ACCESS_TOKEN']='synthetic-bootstrap'
  with self.assertRaises(ValueError):cloud.validate_fleet(values)
 def test_keyring_bootstrap_only_goes_to_bws_child_environment(self):
  values=self.values();rows=[{'key':k,'value':v} for k,v in values.items()]
  calls=[]
  def run(args,**kwargs):
   calls.append((args,kwargs))
   if args[0]=='secret-tool':return SimpleNamespace(returncode=0,stdout='synthetic-bootstrap\n')
   return SimpleNamespace(returncode=0,stdout=json.dumps(rows))
  with patch.object(cloud.subprocess,'run',side_effect=run):self.assertEqual(cloud.fleet_from_bws(),values)
  self.assertEqual(calls[1][1]['env']['BWS_ACCESS_TOKEN'],'synthetic-bootstrap')
  self.assertNotIn('synthetic-bootstrap',calls[1][0])
  self.assertEqual(calls[1][0][-1],cloud.FLEET_PROJECT)
 def test_duplicate_selected_bws_keys_fail_closed(self):
  values=self.values();rows=[{'key':k,'value':v} for k,v in values.items()];rows.append(rows[-1])
  with patch.object(cloud.subprocess,'run',side_effect=[SimpleNamespace(returncode=0,stdout='synthetic-bootstrap'),SimpleNamespace(returncode=0,stdout=json.dumps(rows))]):
   with self.assertRaises(RuntimeError):cloud.fleet_from_bws()
 def test_activation_guard_has_no_subprocess_side_effect(self):
  with patch.object(cloud.sys,'argv',['grafana-cloud.py','activate-fleet']),patch.object(cloud.subprocess,'run') as run:
   with self.assertRaisesRegex(RuntimeError,'STOP:'):
    cloud.main()
   run.assert_not_called()
