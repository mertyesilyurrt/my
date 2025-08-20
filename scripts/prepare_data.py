import argparse
import hashlib
import os
import sys
import zipfile
from pathlib import Path

import requests
import yaml

BASE = Path(__file__).resolve().parents[1]
DATA_DIR = BASE / 'data-clean'
DOWNLOADS = DATA_DIR / 'downloads'
RAW = BASE / 'gctg-data-clean'


def md5sum(path: Path) -> str:
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def ensure_dirs():
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)


def download_resource(url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def extract_zip(zip_path: Path, out_dir: Path):
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(out_dir)


def prepare_from_yaml(cfg_path: Path):
    class IgnoreUnknown(yaml.SafeLoader):
        pass

    # Treat any unknown tag as plain data (scalar/seq/map)
    def ignore(loader, tag_suffix, node):
        if isinstance(node, yaml.ScalarNode):
            return loader.construct_scalar(node)
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node)
        if isinstance(node, yaml.MappingNode):
            return loader.construct_mapping(node)
        return None

    IgnoreUnknown.add_multi_constructor('', ignore)

    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg = yaml.load(f, Loader=IgnoreUnknown)

    if not isinstance(cfg, dict):
        print('Config root must be a mapping/dict.', file=sys.stderr)
        sys.exit(1)

    resources_node = cfg.get('resources') or {}
    resources = []
    if isinstance(resources_node, dict):
        resources = resources_node.get('gaze') or []
    elif isinstance(resources_node, list):
        resources = resources_node

    if not isinstance(resources, list) or not resources:
        print('No gaze resources defined in YAML; assuming data already present.')
        return

    ensure_dirs()

    for res in resources:
        url = res['resource']
        filename = res['filename']
        expected_md5 = res.get('md5')
        dest = DOWNLOADS / filename

        if not dest.exists():
            print(f'Downloading {url} -> {dest}')
            download_resource(url, dest)
        else:
            print(f'Found existing download: {dest}')

        if expected_md5:
            if not dest.exists():
                print(f'Expected download {dest} not found after attempt.', file=sys.stderr)
                sys.exit(1)

            actual = md5sum(dest)
            if actual != expected_md5:
                print(f'MD5 mismatch for {dest}: {actual} != {expected_md5}', file=sys.stderr)
                # Attempt one re-download in case the cached file is corrupt/partial
                try:
                    print('Removing corrupt download and re-downloading...')
                    dest.unlink()
                except Exception:
                    pass
                print(f'Re-downloading {url} -> {dest}')
                download_resource(url, dest)

                if not dest.exists():
                    print(f'Failed to download {dest} on retry.', file=sys.stderr)
                    sys.exit(1)

                actual = md5sum(dest)
                if actual != expected_md5:
                    print(f'MD5 mismatch after re-download for {dest}: {actual} != {expected_md5}', file=sys.stderr)
                    sys.exit(1)
                else:
                    print('MD5 verified after re-download.')
            else:
                print('MD5 verified.')

        if dest.suffix.lower() == '.zip':
            print(f'Extracting {dest} -> {RAW}')
            extract_zip(dest, BASE)
            # Expect directory gctg-data-clean/ at BASE after extraction
            expected_dir = BASE / 'gctg-data-clean'
            if not expected_dir.exists():
                print('Expected directory gctg-data-clean/ not found after extraction.', file=sys.stderr)
                sys.exit(1)
            else:
                print('Data extracted to gctg-data-clean/.')


def main():
    parser = argparse.ArgumentParser(description='Prepare data for StudyPipeline from gctg-clean.yaml')
    parser.add_argument('--config', type=str, default=str(BASE / 'gctg-clean.yaml'))
    args = parser.parse_args()
    prepare_from_yaml(Path(args.config))


if __name__ == '__main__':
    main()
