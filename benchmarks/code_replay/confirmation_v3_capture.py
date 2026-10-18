"""Full bounded source capture after verified case-descendant termination."""
import base64
from hashlib import sha256
import json
from pathlib import Path
import re
import stat


def git_metadata(root):
    # Read bounded metadata without executing Git/config/hooks from a solver's
    # mutable repository. The initial metadata is frozen before any inference.
    from atmem.knowledge.projections import read_authorized_file
    head=read_authorized_file(Path(root),'.git/HEAD',4096)
    match=re.fullmatch(rb'ref: (refs/heads/[A-Za-z0-9_/-]+)\n',head)
    if match is None:raise ValueError('initial named branch metadata required')
    name=match.group(1).decode('ascii')
    reference=read_authorized_file(Path(root),'.git/'+name,4096)
    if re.fullmatch(rb'[0-9a-f]{40}\n',reference) is None:raise ValueError('bounded original Git reference required')
    return {'head_base64':base64.b64encode(head).decode(),'reference_path':name,
            'reference_base64':base64.b64encode(reference).decode(),'commit':reference.decode().strip()}


def captured_case(case,*,writers_stopped,expected_git=None,process_scope=None):
    from benchmarks.code_replay.source_capture import capture_stopped_workspace
    root=Path(case['workspace'])
    if (root!=Path(case['root'])/'workspace' or root.is_symlink()
            or not str(root).startswith('/home/jt/atmem-benchmark-runtime-20261018/confirmation-stage-v3/block-')):
        raise ValueError('exact fresh v3 source origin required')
    if process_scope is not None:
        from benchmarks.code_replay.confirmation_v3_process_scope import populated
        if populated(Path(process_scope)):raise ValueError('case descendants still live; capture prohibited')
    files=capture_stopped_workspace(root,writers_stopped=writers_stopped)
    modes={name:'100755' if (root/name).stat().st_mode&0o111 else '100644' for name in files}
    try:metadata=git_metadata(root);metadata_error=None
    except (ValueError,OSError) as exc:metadata=None;metadata_error=type(exc).__name__
    encoded={name:base64.b64encode(raw).decode() for name,raw in files.items()}
    if process_scope is not None and populated(Path(process_scope)):
        raise ValueError('case descendants resumed during capture')
    return {'workspace':str(root),'case_root':case['root'],'files_base64':encoded,'modes':modes,
        'files':len(files),'bytes':sum(map(len,files.values())),
        'source_sha256':sha256(json.dumps(encoded,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'git_metadata':metadata,'git_metadata_error':metadata_error,
        'git_metadata_unchanged':expected_git is None or metadata==expected_git,
        'temporary_cli_auth_absent':not (Path(case['cli_home'])/'auth.json').exists(),
        'writer_processes_observed':False if process_scope is not None else None,
        'process_scope':process_scope,
        'writer_assurance':'verified empty root-owned case cgroup at capture boundaries' if process_scope is not None
                           else 'caller-declared stopped pre-inference source; descriptor-relative race checks'}
