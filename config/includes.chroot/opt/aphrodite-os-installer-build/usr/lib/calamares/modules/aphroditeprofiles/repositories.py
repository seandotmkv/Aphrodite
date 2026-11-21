"""User-selected official repositories; never execute remote installer scripts."""
from pathlib import Path

BRAVE_KEY = 'https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg'
BRAVE_SOURCE = '''Types: deb
URIs: https://brave-browser-apt-release.s3.brave.com/
Suites: stable
Components: main
Architectures: amd64
Signed-By: /usr/share/keyrings/brave-browser-archive-keyring.gpg
'''


def configure_brave(target):
    # Key trust is established over vendor HTTPS as in Brave's official Debian
    # instructions. The key is scoped to this one repository, never apt-key.
    target.command('python3', '-c', '''import hashlib,os,pathlib,sys,tempfile,urllib.request
url=sys.argv[1]
with urllib.request.urlopen(url,timeout=20) as response:
    data=response.read(65537)
if not 1024 <= len(data) <= 65536:
    raise SystemExit("Invalid Brave signing-key size")
p=pathlib.Path('/usr/share/keyrings/brave-browser-archive-keyring.gpg')
p.parent.mkdir(parents=True,exist_ok=True)
with tempfile.NamedTemporaryFile(dir=p.parent,delete=False) as f:
    temp=pathlib.Path(f.name);f.write(data)
try:
    temp.chmod(0o644);temp.replace(p)
finally:
    temp.unlink(missing_ok=True)
print("Brave vendor key SHA-256:",hashlib.sha256(data).hexdigest())
''', BRAVE_KEY, timeout=60)
    source = Path(target.root) / 'etc/apt/sources.list.d/aphrodite-brave.sources'
    source.parent.mkdir(parents=True, exist_ok=True)
    if source.exists() and source.read_text() != BRAVE_SOURCE:
        raise ValueError('Existing Brave source differs; preserve it and review manually')
    source.write_text(BRAVE_SOURCE)
    # Refresh only the selected vendor source. An outage must not block other
    # applications using Debian's already refreshed, signed indexes.
    target.apt('-o', 'Dir::Etc::sourcelist=/etc/apt/sources.list.d/aphrodite-brave.sources',
               '-o', 'Dir::Etc::sourceparts=-', '-o', 'APT::Update::Error-Mode=any', 'update', timeout=180)
