"""Archive explicit retired benchmark directories; never delete automatically.

Uses existing recipient-encrypted/signed archive framing. Plain compressed tar
bytes exist only in memory. Keys and the path manifest stay on internal storage.
Recovery validates exact compressed bytes in a separate process before an
operator may reclaim any named source. This is not a benchmark score artifact.
"""
import argparse
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import stat
import tarfile

from benchmarks.code_replay.archive import seal, open_archive, MAX_BYTES


def inventory(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError("explicit regular source directory required")
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            result[relative] = ["symlink", os.readlink(path)]
        elif stat.S_ISREG(info.st_mode):
            digest = sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(65536), b""):
                    digest.update(block)
            result[relative] = ["file", info.st_size, digest.hexdigest()]
        elif stat.S_ISDIR(info.st_mode):
            result[relative] = ["directory"]
        else:
            raise ValueError("special file in retired benchmark directory")
    return result


def compressed_snapshot(root, before):
    target = io.BytesIO()
    with tarfile.open(fileobj=target, mode="w:gz", dereference=False) as archive:
        archive.add(root, arcname=root.name)
    raw = target.getvalue()
    if len(raw) > MAX_BYTES:
        raise ValueError("compressed scratch exceeds existing archive budget")
    if inventory(root) != before:
        raise ValueError("scratch changed while archiving")
    return raw


def recover(manifest_path):
    keys = manifest_path.parent
    manifest = json.loads(open_archive(json.loads(manifest_path.read_bytes()),
        run_id="scratch-retention-manifest-v1",
        recipient_secret_key=(keys / "recipient.secret").read_bytes(),
        trusted_signing_public_key=(keys / "signing.public").read_bytes()))
    total = 0
    for row in manifest["rows"]:
        bundle = json.loads(Path(row["archive"]).read_bytes())
        raw = open_archive(bundle, run_id=row["run_id"],
            recipient_secret_key=(keys / "recipient.secret").read_bytes(),
            trusted_signing_public_key=(keys / "signing.public").read_bytes())
        if sha256(raw).hexdigest() != row["compressed_sha256"]:
            raise ValueError("recovered scratch bytes differ")
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            observed = {}
            root_name = Path(row["source"]).name
            for member in archive:
                if member.name == root_name:
                    continue
                if not member.name.startswith(root_name + "/"):
                    raise ValueError("archive member outside declared root")
                relative = member.name[len(root_name) + 1:]
                if member.isdir():
                    observed[relative] = ["directory"]
                elif member.issym():
                    observed[relative] = ["symlink", member.linkname]
                elif member.isfile() or member.islnk():
                    digest, size = sha256(), 0
                    stream = archive.extractfile(member)
                    for block in iter(lambda: stream.read(65536), b""):
                        digest.update(block); size += len(block)
                    observed[relative] = ["file", size, digest.hexdigest()]
                else:
                    raise ValueError("unsupported recovered member")
            if observed != row["inventory"]:
                raise ValueError("recovered file inventory differs")
        total += len(observed)
    return {"archives_verified": len(manifest["rows"]), "entries_verified": total,
            "manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
            "source_deletion": "not_performed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--recover", type=Path)
    args = parser.parse_args()
    if args.recover:
        print(json.dumps(recover(args.recover)))
        return
    plan = json.loads(args.plan.read_bytes())
    keys, output = Path(plan["key_root"]), Path(plan["archive_root"])
    if Path("/Volumes") in keys.resolve().parents or Path("/Volumes") in args.plan.resolve().parents:
        raise ValueError("keys and source manifest must stay internal")
    keys.mkdir(mode=0o700, parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=False)
    from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair
    public, secret = generate_recipient_keypair()
    sign_public, sign_secret = generate_signing_keypair()
    for name, raw in (("recipient.public", public), ("recipient.secret", secret),
                      ("signing.public", sign_public), ("signing.secret", sign_secret)):
        with (keys / name).open("xb") as stream:
            os.chmod(stream.name, 0o600)
            stream.write(raw)
    manifest = {"key_root": str(keys), "rows": [], "purpose": "retired_benchmark_scratch_retention"}
    manifest_path = keys / "manifest.encrypted.json"
    for index, source in enumerate(plan["sources"]):
        root = Path(source)
        before = inventory(root)
        raw = compressed_snapshot(root, before)
        run_id = plan["run_id"] + "-" + str(index)
        bundle = seal(raw, run_id=run_id, recipient_public_key=public,
                      signing_public_key=sign_public, signing_secret_key=sign_secret)
        target = output / (str(index) + ".encrypted.json")
        with target.open("x") as stream:
            json.dump(bundle, stream, separators=(",", ":"))
        manifest["rows"].append({"source": str(root), "inventory": before,
            "archive": str(target), "run_id": run_id, "compressed_sha256": sha256(raw).hexdigest()})
        encrypted_manifest = seal(json.dumps(manifest, separators=(",", ":")).encode(),
            run_id="scratch-retention-manifest-v1", recipient_public_key=public,
            signing_public_key=sign_public, signing_secret_key=sign_secret)
        manifest_path.write_text(json.dumps(encrypted_manifest, separators=(",", ":")))
        print(json.dumps({"archived": index + 1, "compressed_bytes": len(raw)}), flush=True)
    print(json.dumps({"manifest": str(manifest_path), "source_deletion": "not_performed"}), flush=True)


if __name__ == "__main__":
    main()
