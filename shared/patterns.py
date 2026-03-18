"""Build pattern listesi - varsayilan + kullanici eklentileri."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional, Tuple, List

from shared.logging import log


DEFAULT_PATTERNS: List[Tuple[str, str, str]] = [
    # npm / yarn / pnpm / bun
    (r'\bnpm\s+(run\s+)?(build|compile|bundle|pack|publish)',    'npm build',      'NPM'),
    (r'\byarn\s+(run\s+)?(build|compile|bundle|pack|publish)',   'yarn build',     'YARN'),
    (r'\bpnpm\s+(run\s+)?(build|compile|bundle|pack|publish)',   'pnpm build',     'PNPM'),
    (r'\bbun\s+(run\s+)?(build|compile|bundle)',                 'bun build',      'BUN'),
    (r'\bnpm\s+install\b',                                       'npm install',    'NPM'),
    (r'\byarn\s+install\b',                                      'yarn install',   'YARN'),
    (r'\bpnpm\s+install\b',                                      'pnpm install',   'PNPM'),
    (r'\bbun\s+install\b',                                       'bun install',    'BUN'),

    # Monorepo araclari
    (r'\bnx\s+(build|deploy|serve|test|lint)\b',                 'nx build',       'NX'),
    (r'\bturbo\s+(build|test|lint|dev)\b',                       'turbo build',    'TURBO'),
    (r'\blerna\s+(build|publish|run\s+build)\b',                 'lerna build',    'LERNA'),

    # Docker
    (r'\bdocker\s+build\b',                                      'docker build',   'DOCKER'),
    (r'\bdocker\s+compose\s+(up|build|push)',                    'docker compose', 'DOCKER'),
    (r'\bdocker\s+push\b',                                       'docker push',    'DOCKER'),

    # Deploy platformlari
    (r'\bvercel\s+(deploy|build|--prod)',                        'vercel deploy',  'VERCEL'),
    (r'\bnetlify\s+deploy\b',                                    'netlify deploy', 'NETLIFY'),
    (r'\bflyctl\s+deploy\b',                                     'fly deploy',     'FLY'),
    (r'\bwrangler\s+(deploy|publish)\b',                         'wrangler deploy','CF'),
    (r'\baws\s+(deploy|cloudformation|s3\s+sync|ecr)',           'aws deploy',     'AWS'),
    (r'\bgcloud\s+(app\s+deploy|run\s+deploy|builds)',           'gcloud deploy',  'GCP'),
    (r'\bheroku\s+(deploy|container:push|releases:output)\b',    'heroku deploy',  'HEROKU'),
    (r'\brailway\s+(up|deploy)\b',                               'railway deploy', 'RAILWAY'),
    (r'\brender\s+deploy\b',                                     'render deploy',  'RENDER'),

    # Infrastructure as Code
    (r'\bterraform\s+(apply|plan|destroy)\b',                    'terraform',      'TF'),
    (r'\bpulumi\s+(up|deploy|preview)\b',                        'pulumi up',      'PULUMI'),
    (r'\bansible-playbook\b',                                    'ansible',        'ANSIBLE'),
    (r'\bkubectl\s+(apply|rollout|deploy)\b',                    'kubectl deploy', 'K8S'),
    (r'\bhelm\s+(install|upgrade|rollout)\b',                    'helm deploy',    'HELM'),

    # Build araclari
    (r'\bcargo\s+(build|compile|publish)',                        'cargo build',    'RUST'),
    (r'\bcargo\s+test\b',                                        'cargo test',     'TEST'),
    (r'\bgo\s+build\b',                                          'go build',       'GO'),
    (r'\bmake\b(?!\s+-n)',                                        'make',           'MAKE'),
    (r'\bcmake\s+--build\b',                                     'cmake build',    'CMAKE'),
    (r'\bgradle(w)?\s+(build|assemble|publish)',                  'gradle build',   'GRADLE'),
    (r'\bmvn\s+(package|install|deploy|compile)',                 'maven build',    'MVN'),
    (r'\bpip\s+install\b',                                       'pip install',    'PIP'),
    (r'\bpoetry\s+(install|build|publish)',                       'poetry build',   'POETRY'),
    (r'\buv\s+(sync|install|build)\b',                           'uv install',     'UV'),
    (r'\bswift\s+build\b',                                       'swift build',    'SWIFT'),
    (r'\bxcodebuild\b',                                          'xcode build',    'XCODE'),

    # Bundlers
    (r'\bwebpack\b',                                              'webpack',        'WEBPACK'),
    (r'\besbuild\b',                                              'esbuild',        'ESBUILD'),
    (r'\brollup\b',                                               'rollup',         'ROLLUP'),
    (r'\bvite\s+build\b',                                         'vite build',     'VITE'),
    (r'\bparcel\s+(build|watch)\b',                               'parcel build',   'PARCEL'),
    (r'\btsup\b',                                                 'tsup',           'TSUP'),
    (r'\bunbuild\b',                                              'unbuild',        'UNBUILD'),

    # Deno
    (r'\bdeno\s+(compile|bundle)\b',                              'deno build',     'DENO'),
    (r'\bdeno\s+test\b',                                          'deno test',      'TEST'),

    # Package managers extra
    (r'\bnpm\s+ci\b',                                             'npm ci',         'NPM'),
    (r'\bnpm\s+publish\b',                                        'npm publish',    'NPM'),
    (r'\byarn\s+add\b',                                           'yarn add',       'YARN'),
    (r'\bpnpm\s+add\b',                                           'pnpm add',       'PNPM'),
    (r'\bbun\s+add\b',                                             'bun add',        'BUN'),

    # Containers extra
    (r'\bpodman\s+build\b',                                       'podman build',   'PODMAN'),
    (r'\bbuildah\s+bud\b',                                        'buildah build',  'BUILDAH'),

    # Ruby
    (r'\bbundle\s+install\b',                                     'bundle install', 'RUBY'),
    (r'\brails\s+assets:precompile\b',                            'rails assets',   'RUBY'),
    (r'\brake\b',                                                  'rake',           'RUBY'),

    # PHP
    (r'\bcomposer\s+(install|update|require)\b',                  'composer',       'PHP'),
    (r'\bartisan\b',                                               'artisan',        'PHP'),
    (r'\bphpunit\b',                                               'phpunit',        'TEST'),

    # .NET
    (r'\bdotnet\s+(build|publish)\b',                             'dotnet build',   'DOTNET'),
    (r'\bdotnet\s+test\b',                                        'dotnet test',    'TEST'),
    (r'\bdotnet\s+restore\b',                                     'dotnet restore', 'DOTNET'),

    # Misc build systems
    (r'\bbazel\s+build\b',                                        'bazel build',    'BAZEL'),
    (r'\bbuck\s+build\b',                                         'buck build',     'BUCK'),
    (r'\bninja\b',                                                 'ninja build',    'NINJA'),
    (r'\bmeson\s+(setup|compile)\b',                              'meson build',    'MESON'),
    (r'\bant\s+(build|compile|jar)\b',                            'ant build',      'ANT'),

    # Test araclari
    (r'\bjest\b',                                                'jest tests',     'TEST'),
    (r'\bpytest\b',                                              'pytest',         'TEST'),
    (r'\bvitest\b',                                              'vitest',         'TEST'),
    (r'\bmocha\b',                                               'mocha tests',    'TEST'),
    (r'\bplaywright\s+test\b',                                   'playwright',     'TEST'),
    (r'\bcypress\s+run\b',                                       'cypress',        'TEST'),
    (r'\bgo\s+test\b',                                           'go test',        'TEST'),

    # Git
    (r'\bgit\s+push\b',                                          'git push',       'GIT'),
]

# Kullanici eklentileri dosyasi
_CUSTOM_PATTERNS_FILE = Path.home() / ".claude" / "monitor_patterns.json"


def load_patterns() -> List[Tuple[str, str, str]]:
    """Varsayilan + kullanici pattern'larini birlesik dondur."""
    patterns = list(DEFAULT_PATTERNS)

    if _CUSTOM_PATTERNS_FILE.exists():
        try:
            custom = json.loads(_CUSTOM_PATTERNS_FILE.read_text())
            for p in custom:
                regex = p.get("regex", "")
                # Regex gecerliligini kontrol et
                try:
                    re.compile(regex)
                except re.error:
                    log("PATTERNS", f"invalid custom regex: {regex!r}")
                    continue
                patterns.insert(0, (regex, p.get("label", "custom"), p.get("tool", "CUSTOM")))
        except (json.JSONDecodeError, OSError) as e:
            log("PATTERNS", f"custom patterns load error: {e}")

    return patterns


def detect_build_command(command: str) -> Optional[Tuple[str, str]]:
    """Komutu pattern listesiyle eslestir. (label, tool) veya None dondur."""
    patterns = load_patterns()
    for pattern, label, tool in patterns:
        try:
            if re.search(pattern, command.strip(), re.IGNORECASE):
                return label, tool
        except re.error:
            continue
    return None


def add_custom_pattern(regex: str, label: str, tool: str) -> bool:
    """Kullanici pattern'i JSON dosyasina ekle."""
    # Regex gecerliligini kontrol et
    try:
        re.compile(regex)
    except re.error:
        return False

    customs = []
    if _CUSTOM_PATTERNS_FILE.exists():
        try:
            customs = json.loads(_CUSTOM_PATTERNS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            customs = []

    customs.append({"regex": regex, "label": label, "tool": tool.upper()})

    try:
        _CUSTOM_PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CUSTOM_PATTERNS_FILE.write_text(json.dumps(customs, indent=2))
        return True
    except OSError:
        return False
