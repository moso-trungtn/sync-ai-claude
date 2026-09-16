"""Shared, local-only PDF cache. Revisions are immutable and keyed by SHA-256."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from datetime import datetime, timezone

DEFAULT_CACHE = Path.home() / '.cache/moso/lender-document-files'


class DocumentCache:
    def __init__(self, root=DEFAULT_CACHE):
        self.root = Path(root)

    def directory(self, fid):
        if not re.fullmatch(r'[A-Za-z0-9_-]{20,}', fid):
            raise ValueError('Invalid Drive file ID')
        return self.root / fid

    def metadata(self, fid):
        path = self.directory(fid) / 'current.json'
        return json.loads(path.read_text()) if path.exists() else None

    def cached(self, fid):
        meta = self.metadata(fid)
        if meta:
            path = self.directory(fid) / (meta['sha256'] + '.pdf')
            if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == meta['sha256']:
                return path
        return None

    def save(self, fid, data, name):
        if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-4096:]:
            raise ValueError('Response is not a complete PDF (possibly a sign-in page)')
        directory = self.directory(fid)
        directory.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(data).hexdigest()
        dest = directory / (digest + '.pdf')
        if not dest.exists() or hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            self.atomic(dest, data)
        meta = {'id': fid, 'name': Path(name).name, 'bytes': len(data), 'sha256': digest,
                'source_url': f'https://drive.google.com/file/d/{fid}/view',
                'retrieved_at': datetime.now(timezone.utc).isoformat(),
                'effective_date': None}
        self.atomic(directory / (digest + '.json'), (json.dumps(meta, indent=2) + '\n').encode())
        self.atomic(directory / 'current.json', (json.dumps(meta, indent=2) + '\n').encode())
        return dest

    @staticmethod
    def atomic(path, data):
        fd, name = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def fetch(self, fid, name, refresh=False):
        existing = self.cached(fid)
        if existing and not refresh:
            return existing
        response = subprocess.run(
            ['curl', '--fail', '--location', '--silent', '--show-error',
             '--proto', '=https', '--proto-redir', '=https', '--max-time', '180',
             f'https://drive.google.com/uc?export=download&id={fid}'],
            capture_output=True, check=True)
        return self.save(fid, response.stdout, name)
