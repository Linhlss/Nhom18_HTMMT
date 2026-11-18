"""Shared helpers for week-1 evidence folders (TV2/TV3/TV4). Standard library only."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NETWORKCTL = ROOT / 'control' / 'networkctl.py'


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def utc_iso(dt=None):
    return (dt or utc_now()).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def run_stamp(dt=None):
    return (dt or utc_now()).strftime('%Y%m%dT%H%M%S%fZ')


def check_label(label):
    if not label or not label.replace('-', '').replace('_', '').isalnum() or len(label) > 40:
        raise ValueError('label: 1-40 letters, digits, "-" or "_"')
    return label


def make_run_dir(area, label):
    """evidence/<area>/<UTC>-<label>/ ; run_id is the folder name."""
    run_id = f'{run_stamp()}-{check_label(label)}'
    out = ROOT / 'evidence' / area / run_id
    out.mkdir(parents=True)
    return run_id, out


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_manifest(folders):
    files = sorted(p for folder in folders for p in (ROOT / folder).rglob('*')
                   if p.is_file() and p.suffix in ('.py', '.json', '.sh', '.md')
                   and '__pycache__' not in p.parts and not p.name.startswith('._'))
    return {str(p.relative_to(ROOT)): sha256_file(p) for p in files}


def _cmd(argv):
    try:
        p = subprocess.run(argv, text=True, capture_output=True, timeout=30)
        return p.stdout.strip() if p.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def environment(extra=None):
    env = {
        'collected_utc': utc_iso(),
        'machine_note': 'Ghi đúng máy thực hiện: VM nào, của ai; không coi là kiểm thử trên máy thành viên khác.',
        'hostname': _cmd(['hostname']),
        'uname': _cmd(['uname', '-a']),
        'os_release': Path('/etc/os-release').read_text() if Path('/etc/os-release').exists() else None,
        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if Path('/proc/sys/kernel/random/boot_id').exists() else None,
        'python': sys.version,
        'packages': _cmd(['dpkg-query', '-W', '-f=${Package}\t${Version}\t${Architecture}\n',
                          'mininet', 'openvswitch-switch', 'python3', 'iperf3', 'iputils-ping']),
        'git_commit': _cmd(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']),
        'git_branch': _cmd(['git', '-C', str(ROOT), 'rev-parse', '--abbrev-ref', 'HEAD']),
        'git_status_short': _cmd(['git', '-C', str(ROOT), 'status', '--short']),
    }
    env.update(extra or {})
    return env


def networkctl(*args, timeout=120):
    """Run networkctl as a subprocess (caller must be root in the Ubuntu VM). Returns parsed JSON + rc."""
    argv = [sys.executable, str(NETWORKCTL), *args]
    p = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
    try:
        data = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {}
    except json.JSONDecodeError:
        data = {'success': False, 'unparsed_stdout': p.stdout}
    return {'argv': argv[1:], 'cli_returncode': p.returncode, 'result': data, 'cli_stderr': p.stderr}


def exec_argv(host, argv, timeout):
    return [sys.executable, str(NETWORKCTL), 'exec', '--timeout', str(timeout), host, '--', *argv]


def chown_to_sudo_user(path):
    if 'SUDO_UID' not in os.environ:
        return
    uid, gid = int(os.environ['SUDO_UID']), int(os.environ['SUDO_GID'])
    path = Path(path)
    for p in [*path.rglob('*'), path]:
        os.chown(p, uid, gid)


def require_vm_root():
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise SystemExit('Run with sudo /usr/bin/python3 inside the Ubuntu VM (networkctl requires root)')
