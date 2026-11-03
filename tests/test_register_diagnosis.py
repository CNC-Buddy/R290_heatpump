"""Audit provenance and the exact read-only Modbus transport used for sampling."""
import importlib.util
import json
from pathlib import Path
import socket
import struct
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('probe_registers', ROOT / 'scripts/probe_unknown_registers.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Socket:
    def __init__(self, response):
        self.response, self.sent = response, []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def settimeout(self, timeout): pass
    def sendall(self, data): self.sent.append(data)
    def recv(self, n):
        data, self.response = self.response[:min(n,3)], self.response[min(n,3):]
        return data


class RegisterDiagnosisTests(unittest.TestCase):
    def test_probe_sends_only_fc03_and_accepts_fragmented_valid_reply(self):
        sock=Socket(struct.pack('>HHHBBBH',1,0,5,2,3,2,65486))
        with patch.object(socket,'create_connection',return_value=sock):
            self.assertEqual(probe.read_registers('configured-proxy',504,2,0x006E,1),(65486,))
        self.assertEqual(sock.sent,[struct.pack('>HHHBBHH',1,0,6,2,3,0x006E,1)])

    def test_rejects_wrong_unit_transaction_payload_and_exception(self):
        for response in [struct.pack('>HHHBBBH',1,0,5,1,3,2,0),
                         struct.pack('>HHHBBBH',2,0,5,2,3,2,0),
                         struct.pack('>HHHBBB',1,0,3,2,0x83,2),
                         struct.pack('>HHHBBBH',1,0,5,2,3,4,0)]:
            with patch.object(socket,'create_connection',return_value=Socket(response)):
                with self.assertRaises(ValueError): probe.read_registers('proxy',504,2,0x006E,1)

    def test_probe_is_bounded_to_documented_realtime_range(self):
        with patch.object(socket,'create_connection') as connect:
            for slave,address,count in [(1,0x0301,1),(1,0xFF,2),(1,0x40,33),(0,0x40,1)]:
                with self.assertRaises(ValueError):probe.read_registers('proxy',504,slave,address,count)
            connect.assert_not_called()
        self.assertEqual(list(probe.blocks([0x6E,0x6F,0x71])),[(0x6E,2),(0x71,1)])

    def test_catalog_keeps_default_sources_and_marks_incomplete_coverage(self):
        catalog=json.loads((ROOT/'custom_components/r290_heatpump/frontend/register-catalog.json').read_text(encoding='utf-8'))
        records=catalog['records']
        p100=next(r for r in records if r.get('code')=='P100')
        self.assertEqual((p100['default_manual'],p100['default_observed']),(50,30))
        self.assertNotIn('my_value',p100)
        self.assertEqual(len([r for r in records if r['unknown']]),128)
        self.assertEqual(len([r for r in records if r['coverage']=='missing']),39)
        self.assertEqual(len([r for r in records if r['section']==4 and r['issues']]),11)
        self.assertTrue(next(r for r in records if r['address']==0x080B)['issues'])
        self.assertTrue(all(len(s['sha256'])==64 for s in catalog['sources']))

    def test_system_help_is_bilingual_and_retains_documented_uncertainty(self):
        catalog=json.loads((ROOT/'custom_components/r290_heatpump/frontend/register-catalog.json').read_text(encoding='utf-8'))
        system={r['code']:r for r in catalog['records'] if r['section']==4}
        self.assertEqual(len(system),263)
        for code,r in system.items():
            with self.subTest(code=code):
                self.assertTrue(r.get('description_de'))
                self.assertTrue(r.get('description_en') or r.get('description'))
        help_data=json.loads((ROOT/'Documentation/system-parameter-help.json').read_text(encoding='utf-8'))['parameters']
        for code,entry in help_data.items():
            with self.subTest(code=code):
                self.assertEqual(entry['address'],system[code]['address'])
                self.assertEqual(system[code]['description_de'],entry['de'])
                self.assertEqual(system[code]['description_en'],entry['en'])
                self.assertTrue(entry['sources'])
                self.assertTrue(all(source['pages'] and all(p>0 for p in source['pages']) for source in entry['sources']))
        for code in ('P097','P163','P248'):
            self.assertEqual(system[code]['explanation_level'],'conflict')
        self.assertEqual(system['P155']['explanation_level'],'reserved')
        self.assertIn('nicht',system['P175']['description_de'])

    def test_explanation_update_preserves_all_system_defaults_ranges_and_addresses(self):
        import openpyxl
        book=openpyxl.load_workbook(next((ROOT/'Documentation').glob('4 *xlsx')),read_only=True,data_only=True)
        try:
            catalog=json.loads((ROOT/'custom_components/r290_heatpump/frontend/register-catalog.json').read_text(encoding='utf-8'))
            system={r['code']:r for r in catalog['records'] if r['section']==4}
            for row in book.active.iter_rows(values_only=True):
                if row[0] not in system:
                    continue
                r=system[row[0]]
                with self.subTest(code=row[0]):
                    self.assertEqual((r['address'],r['min'],r['max'],r['default_manual'],r['default_observed']),
                                     (int(row[1],16),row[5],row[6],row[7],row[8]))
        finally:
            book.close()


if __name__=='__main__': unittest.main()
