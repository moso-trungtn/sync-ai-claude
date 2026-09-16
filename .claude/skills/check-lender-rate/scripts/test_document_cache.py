import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from lender_document_cache import DocumentCache

FID='a'*25
PDF=b'%PDF-1.4\nminimal test fixture\n%%EOF\n'

class CacheTest(unittest.TestCase):
    def test_reuse_no_network_and_revision_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            cache=DocumentCache(root)
            first=cache.save(FID, PDF, '../../matrix.pdf')
            with patch('subprocess.run', side_effect=AssertionError('network called')):
                self.assertEqual(first,cache.fetch(FID,'matrix.pdf'))
            second=cache.save(FID,PDF.replace(b'minimal',b'revised'),'matrix.pdf')
            self.assertNotEqual(first,second)
            self.assertTrue(first.exists())
            self.assertEqual('matrix.pdf',cache.metadata(FID)['name'])
    def test_bad_download_preserves_previous(self):
        with tempfile.TemporaryDirectory() as root:
            cache=DocumentCache(root)
            old=cache.save(FID,PDF,'matrix.pdf')
            for bad in (b'<html>Sign in</html>',b'%PDF-1.4 truncated'):
                with self.assertRaises(ValueError): cache.save(FID,bad,'bad.pdf')
                self.assertEqual(old,cache.cached(FID))
    def test_corrupt_cache_is_not_reused(self):
        with tempfile.TemporaryDirectory() as root:
            cache=DocumentCache(root)
            path=cache.save(FID,PDF,'matrix.pdf')
            path.write_bytes(b'corrupt')
            self.assertIsNone(cache.cached(FID))
    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError): DocumentCache('/tmp').directory('../outside')
    def test_direct_drive_links_deduplicated(self):
        spec=importlib.util.spec_from_file_location('guidelines',Path(__file__).with_name('lender-guidelines.py'))
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        from types import SimpleNamespace
        args=SimpleNamespace(ids=[FID,'https://drive.google.com/file/d/'+FID+'/view'],ids_file=None,lender=None)
        self.assertEqual([FID],mod.read_ids(args))

if __name__=='__main__': unittest.main()
