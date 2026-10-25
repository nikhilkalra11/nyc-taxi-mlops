"""Upload immutable candidate artifacts to S3. No deployment side effects."""
import argparse
import hashlib
import json
from pathlib import Path

import boto3


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--bucket', required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--directory', required=True)
    p.add_argument('--prefix', default='model-registry/candidates')
    args = p.parse_args()
    if not args.run_id.replace('-', '').replace('_', '').isalnum():
        p.error('run-id must be alphanumeric, underscore, or hyphen')
    root = Path(args.directory).resolve()
    if not root.is_dir():
        p.error('directory does not exist')
    s3 = boto3.client('s3')
    manifest = {'run_id': args.run_id, 'files': {}}
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        key = f'{args.prefix.strip("/")}/{args.run_id}/{rel}'
        # Avoid accidental mutation of previously registered candidates.
        try:
            s3.head_object(Bucket=args.bucket, Key=key)
        except s3.exceptions.ClientError as exc:
            if exc.response['Error']['Code'] not in ('404', 'NoSuchKey', 'NotFound'):
                raise
        else:
            raise SystemExit(f'Candidate object already exists: s3://{args.bucket}/{key}')
        data = path.read_bytes()
        s3.put_object(Bucket=args.bucket, Key=key, Body=data)
        manifest['files'][rel] = {'key': key, 'sha256': hashlib.sha256(data).hexdigest()}
    if not manifest['files']:
        raise SystemExit('No candidate files found')
    key = f'{args.prefix.strip("/")}/{args.run_id}/manifest.json'
    s3.put_object(Bucket=args.bucket, Key=key, Body=json.dumps(manifest, indent=2).encode(),
                  ContentType='application/json')
    print(f's3://{args.bucket}/{key}')


if __name__ == '__main__':
    main()
