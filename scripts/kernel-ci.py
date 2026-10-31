#!/usr/bin/env python3
"""Build ARM64 SDIO/USB modules against pinned upstream kernels."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / 'ci/kernels.json'
PROFILES = {
    'sdio': ('CONFIG_SKW_SDIOHAL=m', 'CONFIG_SKW_USB=n', 'skw_sdio_lite'),
    'usb': ('CONFIG_SKW_SDIOHAL=n', 'CONFIG_SKW_USB=m', 'skw_usb_lite'),
}
COMMON = ['CONFIG_SEEKWAVE_BSP_DRIVERS=m', 'CONFIG_SKW_NO_CONFIG=y',
          'CONFIG_WLAN_VENDOR_SWT6621S=m', 'CONFIG_SKW_BT=m',
          'CONFIG_SWT6621S_LOG_DEBUG=y']
STAMP = '.swt6621s-kernel.json'


def entries():
    items = json.loads(MANIFEST.read_text())
    if not isinstance(items, list) or not 1 <= len(items) <= 256:
        raise ValueError('The kernel matrix must contain 1 to 256 entries')
    seen = set()
    for item in items:
        if (not isinstance(item, dict) or set(item) != {'version', 'sha256'} or
                not isinstance(item['version'], str) or
                not re.fullmatch(r'[0-9]+\.[0-9]+(?:\.[0-9]+)?', item['version']) or
                not isinstance(item['sha256'], str) or
                not re.fullmatch(r'[0-9a-f]{64}', item['sha256']) or
                item['version'] in seen):
            raise ValueError(f'Invalid or duplicate kernel entry: {item}')
        seen.add(item['version'])
    return items


def entry(version):
    for item in entries():
        if item['version'] == version:
            return item
    raise ValueError(f'Kernel is not in the manifest: {version}')


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def source_identity(source, item):
    marker = source / '.swt6621s-ci-source.json'
    if marker.exists():
        if json.loads(marker.read_text()) != item:
            raise ValueError('Extracted kernel does not match the manifest')
        return {'archive': item['sha256']}
    # Allow a clean, exact upstream tag for local compilation without downloads.
    git = ['git', '-C', str(source)]
    head = subprocess.check_output(git + ['rev-parse', 'HEAD'], text=True).strip()
    tag = subprocess.check_output(
        git + ['rev-parse', f'refs/tags/v{item["version"]}^{{commit}}'], text=True).strip()
    if head != tag:
        raise ValueError('Kernel checkout does not match the pinned upstream tag')
    subprocess.run(git + ['diff', '--quiet', 'HEAD', '--'], check=True)
    return {'git_commit': head}


def kernel_key(version, source, kernel):
    cross = os.environ.get('CROSS_COMPILE', 'aarch64-linux-gnu-')
    tools = {program: subprocess.check_output([program, '--version'], text=True)
             for program in ['gcc', 'ld', 'make', cross + 'gcc', cross + 'ld']}
    settings = {
        'source': entry(version), 'identity': source_identity(source, entry(version)),
        'architecture': 'arm64', 'host_architecture': platform.machine(), 'tools': tools,
        'source_directory': str(source.resolve()), 'kernel_directory': str(kernel.resolve()),
        'config': digest(ROOT / 'ci/arm64.config'), 'builder': digest(Path(__file__)),
        'flags': {name: os.environ.get(name, '') for name in
                  ['KCFLAGS', 'KCPPFLAGS', 'HOSTCFLAGS', 'HOSTLDFLAGS', 'KBUILD_EXTRA_SYMBOLS']},
    }
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()


def kernel_state(kernel, key):
    return {'key': key, 'files': {name: digest(kernel / name)
                                for name in ['.config', 'vmlinux', 'Module.symvers']}}


def kernel_cache_valid(kernel, key):
    try:
        return json.loads((kernel / STAMP).read_text()) == kernel_state(kernel, key)
    except (OSError, ValueError):
        return False


def fetch(args):
    item = entry(args.version)
    cache, source = args.cache.resolve(), args.source.resolve()
    if source.exists():
        raise ValueError(f'Source destination already exists: {source}')
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / f'linux-{args.version}.tar.xz'
    if archive.exists() and digest(archive) != item['sha256']:
        archive.unlink()
    if not archive.exists():
        url = (f'https://cdn.kernel.org/pub/linux/kernel/v{args.version.split(".")[0]}.x/'
               f'{archive.name}')
        partial = archive.with_suffix('.xz.part')
        subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location', '--retry', '3',
                        '--retry-all-errors',
                        '--connect-timeout', '30', '--max-time', '900',
                        '--output', str(partial), url], check=True)
        if digest(partial) != item['sha256']:
            partial.unlink()
            raise ValueError(f'SHA256 mismatch for {url}')
        partial.replace(archive)
    source.mkdir(parents=True)
    subprocess.run(['tar', '-xJf', str(archive), '--strip-components=1',
                    '-C', str(source)], check=True)
    (source / '.swt6621s-ci-source.json').write_text(json.dumps(item) + '\n')
    print(f'Verified and extracted Linux {args.version}')


def run(command, log):
    print(f'Running {log.name}: {" ".join(map(str, command))}', flush=True)
    with log.open('w') as stream:
        stream.write('$ ' + ' '.join(map(str, command)) + '\n')
        stream.flush()
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True)


def module_details(module, name, release):
    with module.open('rb') as stream:
        header = stream.read(20)
    if header[:6] != b'\x7fELF\x02\x01' or int.from_bytes(header[18:20], 'little') != 183:
        raise ValueError(f'{name} is not an ARM64 module')
    vermagic = subprocess.check_output(['modinfo', '-F', 'vermagic', str(module)],
                                       text=True).strip()
    if not vermagic or vermagic.split()[0] != release:
        raise ValueError(f'{name} vermagic mismatch: {vermagic}')
    if subprocess.check_output(['modinfo', '-F', 'name', str(module)], text=True).strip() != name:
        raise ValueError(f'Unexpected module name: {module}')
    return {'name': name, 'vermagic': vermagic, 'sha256': digest(module)}


def build(args):
    item = entry(args.version)
    source, output = args.source.resolve(), args.output.resolve()
    if any(parent == output or output in parent.parents for parent in [ROOT, source]):
        raise ValueError('Build output must not contain the repository or kernel sources')
    kernel, logs = output / 'kernel', output / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    (output / 'result.json').unlink(missing_ok=True)
    if (output / 'modules').exists():
        shutil.rmtree(output / 'modules')
    report = {'version': args.version, 'architecture': 'arm64',
              'kernel': 'NOT RUN', 'profiles': {name: 'NOT RUN' for name in PROFILES},
              'module_details': {}, 'result': 'FAIL'}
    phase = 'config'
    try:
        git = ['git', '-C', str(ROOT)]
        report['driver_commit'] = subprocess.check_output(git + ['rev-parse', 'HEAD'], text=True).strip()
        report['driver_dirty'] = bool(subprocess.check_output(git + ['status', '--porcelain'], text=True))
        report['source_identity'] = source_identity(source, item)
        cross = os.environ.get('CROSS_COMPILE', 'aarch64-linux-gnu-')
        report['compiler'] = subprocess.check_output([cross + 'gcc', '--version'], text=True).splitlines()[0]
        key = kernel_key(args.version, source, kernel)
        reused = kernel_cache_valid(kernel, key)
        report.update(kernel_cache_key=key, kernel_cache_reused=reused)
        if kernel.exists() and not reused:
            shutil.rmtree(kernel)
        kernel.mkdir(parents=True, exist_ok=True)
        make = ['make', '-C', str(source), f'O={kernel}', 'ARCH=arm64',
                f'CROSS_COMPILE={cross}', 'LOCALVERSION=-swt6621s-ci',
                'KBUILD_MODPOST_WARN=', 'KBUILD_BUILD_USER=swt6621s', 'KBUILD_BUILD_HOST=ci']
        if reused:
            (logs / 'config.log').write_text('Reusing validated kernel configuration and build.\n')
        else:
            run(make + [f'KCONFIG_ALLCONFIG={ROOT / "ci/arm64.config"}', 'allnoconfig'],
                logs / 'config.log')
        config = (kernel / '.config').read_text()
        for symbol in ['MODULES', 'MODULE_UNLOAD', 'MODVERSIONS', 'CFG80211', 'CFG80211_WEXT',
                       'BT', 'MMC', 'USB', 'GPIOLIB', 'FW_LOADER', 'RTC_LIB']:
            if not re.search(rf'^CONFIG_{symbol}=[ym]$', config, re.M):
                raise ValueError(f'Missing CONFIG_{symbol}')
        release = subprocess.check_output(make + ['-s', 'kernelrelease'], text=True).strip()
        base = args.version + ('.0' if args.version.count('.') == 1 else '')
        if release != base + '-swt6621s-ci':
            raise ValueError(f'Unexpected kernel release: {release}')
        report['kernel_release'] = release
        phase = 'kernel'
        run(make + [f'-j{args.jobs}', 'vmlinux', 'modules'], logs / 'kernel.log')
        for name in ['vmlinux', 'Module.symvers']:
            if not (kernel / name).is_file() or not (kernel / name).stat().st_size:
                raise ValueError(f'Kernel build did not produce {name}')
        pending = kernel / (STAMP + '.tmp')
        pending.write_text(json.dumps(kernel_state(kernel, key), sort_keys=True) + '\n')
        pending.replace(kernel / STAMP)
        report['kernel'] = 'PASS'
        for profile, (sdio, usb, transport) in PROFILES.items():
            phase = profile
            driver = output / profile
            if driver.exists():
                shutil.rmtree(driver)
            driver.mkdir()
            shutil.copy2(ROOT / 'Makefile', driver / 'Makefile')
            for directory in ['drivers', 'include']:
                shutil.copytree(ROOT / directory, driver / directory,
                                ignore=shutil.ignore_patterns('*.o', '*.o.*', '*.ko', '*.mod',
                                    '*.mod.c', '.*.cmd', 'Module.symvers', 'modules.order',
                                    '.tmp_versions', 'version.h'))
            run(make + [f'M={driver}', f'-j{args.jobs}'] + COMMON + [sdio, usb, 'modules'],
                logs / (profile + '.log'))
            modules = {transport: 'drivers/seekwaveplatform_lite',
                       'swt6621s_wifi': 'drivers/swt6621s_wifi', 'skwbt': 'drivers/swtbt4l'}
            details = {}
            for name, directory in modules.items():
                module = driver / directory / (name + '.ko')
                details[name] = module_details(module, name, release)
                if args.keep_modules:
                    artifacts = output / 'modules' / profile
                    artifacts.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(module, artifacts / module.name)
            report['module_details'][profile] = details
            report['profiles'][profile] = 'PASS'
        report['result'] = 'PASS'
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        report.update(failed_stage=phase, error=str(error))
        if phase == 'kernel':
            report['kernel'] = 'FAIL'
        elif phase in PROFILES:
            report['profiles'][phase] = 'FAIL'
        log = logs / (phase + '.log')
        if log.exists():
            print('\n'.join(log.read_text(errors='replace').splitlines()[-80:]), file=sys.stderr)
        print(f'Linux {args.version} {phase}: {error}', file=sys.stderr)
    finally:
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f'Linux {args.version}: {report["result"]}', flush=True)
    return 0 if report['result'] == 'PASS' else 1


def summarize(args):
    versions = args.versions or [item['version'] for item in entries()]
    print('| Linux / ARM64 | Kernel | SDIO + Wi-Fi + BT | USB + Wi-Fi + BT | Result |')
    print('| --- | --- | --- | --- | --- |')
    reports = {}
    for path in args.results.rglob('result.json'):
        report = json.loads(path.read_text())
        reports.setdefault(report['version'], []).append(report)
    success = True
    for version in versions:
        entry(version)
        candidates = reports.get(version, [])
        if len(candidates) != 1:
            reason = 'missing result' if not candidates else 'duplicate results'
            print(f'| {version} | NOT RUN | NOT RUN | NOT RUN | FAIL: {reason} |')
            success = False
            continue
        result = candidates[0]
        profiles = result.get('profiles', {})
        passed = result.get('kernel') == result.get('result') == 'PASS'
        for profile, (_, _, transport) in PROFILES.items():
            details = result.get('module_details', {}).get(profile, {})
            passed = passed and profiles.get(profile) == 'PASS'
            passed = passed and set(details) == {transport, 'swt6621s_wifi', 'skwbt'}
        success = success and passed
        print(f'| {version} | {result.get("kernel", "NOT RUN")} | '
              f'{profiles.get("sdio", "NOT RUN")} | {profiles.get("usb", "NOT RUN")} | '
              f'{"PASS" if passed else "FAIL"} |')
    return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('matrix')
    for command in ['cache-key', 'cache-ready']:
        cache = commands.add_parser(command)
        cache.add_argument('version')
        cache.add_argument('source', type=Path)
        cache.add_argument('kernel', type=Path)
    prepare = commands.add_parser('fetch')
    prepare.add_argument('version')
    prepare.add_argument('cache', type=Path)
    prepare.add_argument('source', type=Path)
    compile_kernel = commands.add_parser('build')
    compile_kernel.add_argument('version')
    compile_kernel.add_argument('source', type=Path)
    compile_kernel.add_argument('output', type=Path)
    compile_kernel.add_argument('--jobs', type=int, default=2)
    compile_kernel.add_argument('--keep-modules', action='store_true')
    summary = commands.add_parser('summary')
    summary.add_argument('results', type=Path)
    summary.add_argument('versions', nargs='*')
    args = parser.parse_args()
    try:
        if args.command == 'matrix':
            print(json.dumps({'include': entries()}, separators=(',', ':')))
        elif args.command in ['cache-key', 'cache-ready']:
            key = kernel_key(args.version, args.source, args.kernel)
            print(key if args.command == 'cache-key' else
                  str(kernel_cache_valid(args.kernel, key)).lower())
        elif args.command == 'fetch':
            fetch(args)
        elif args.command == 'build':
            if args.jobs < 1:
                parser.error('--jobs must be positive')
            return build(args)
        else:
            return summarize(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
