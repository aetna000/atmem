"""Owner-only provider files: POSIX modes or verified Windows protected DACLs.

No shell, ACL-text parsing, extra dependency or permission-check bypass. Windows
administrators/SYSTEM are trusted OS principals, not ordinary additional users.
Unknown ACE types and unsupported filesystems fail closed.
"""
from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import stat


@lru_cache(maxsize=1)
def _windows_api():
    import ctypes as c
    from ctypes import wintypes as w
    adv=c.WinDLL('advapi32',use_last_error=True)
    kernel=c.WinDLL('kernel32',use_last_error=True)
    ptr=c.c_void_p; out=c.POINTER(ptr)
    signatures={
        'OpenProcessToken':([w.HANDLE,w.DWORD,c.POINTER(w.HANDLE)],w.BOOL),
        'GetTokenInformation':([w.HANDLE,c.c_int,ptr,w.DWORD,c.POINTER(w.DWORD)],w.BOOL),
        'ConvertSidToStringSidW':([ptr,c.POINTER(w.LPWSTR)],w.BOOL),
        'ConvertStringSecurityDescriptorToSecurityDescriptorW':([w.LPCWSTR,w.DWORD,out,c.POINTER(w.DWORD)],w.BOOL),
        'GetSecurityDescriptorDacl':([ptr,c.POINTER(w.BOOL),out,c.POINTER(w.BOOL)],w.BOOL),
        'GetSecurityDescriptorOwner':([ptr,out,c.POINTER(w.BOOL)],w.BOOL),
        'GetSecurityDescriptorControl':([ptr,c.POINTER(w.WORD),c.POINTER(w.DWORD)],w.BOOL),
        'GetNamedSecurityInfoW':([w.LPCWSTR,c.c_int,w.DWORD,out,out,out,out,out],w.DWORD),
        'SetNamedSecurityInfoW':([w.LPWSTR,c.c_int,w.DWORD,ptr,ptr,ptr,ptr],w.DWORD),
        'GetAce':([ptr,w.DWORD,out],w.BOOL),
    }
    for name,(args,result) in signatures.items():
        function=getattr(adv,name);function.argtypes=args;function.restype=result
    kernel.GetCurrentProcess.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
    kernel.LocalFree.argtypes=[ptr];kernel.LocalFree.restype=ptr
    return c,w,adv,kernel


def _sid_text(sid):
    c,w,adv,kernel=_windows_api()
    text=w.LPWSTR()
    if not sid or not adv.ConvertSidToStringSidW(sid,c.byref(text)):
        raise OSError('Windows SID verification failed')
    try:return text.value
    finally:kernel.LocalFree(c.cast(text,c.c_void_p))


def _current_sid():
    c,w,adv,kernel=_windows_api()
    token=w.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(),8,c.byref(token)):
        raise OSError('Windows process identity unavailable')
    try:
        size=w.DWORD()
        adv.GetTokenInformation(token,1,None,0,c.byref(size))
        if not 0<size.value<65536:raise OSError('Windows token size invalid')
        data=c.create_string_buffer(size.value)
        if not adv.GetTokenInformation(token,1,data,size,c.byref(size)):
            raise OSError('Windows process identity unavailable')
        return _sid_text(c.cast(data,c.POINTER(c.c_void_p))[0])
    finally:kernel.CloseHandle(token)


def _ordinary(path):
    info=Path(path).lstat()
    return (not stat.S_ISLNK(info.st_mode)
        and not getattr(info,'st_file_attributes',0)&0x400
        and (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)))


def private_path(path):
    """Recheck current permissions; never cache a filesystem ACL verdict."""
    path=Path(path)
    try:
        if not _ordinary(path):return False
        info=path.stat()
        if os.name!='nt':
            return not info.st_mode&0o077 and info.st_uid==os.getuid()
        c,w,adv,kernel=_windows_api()
        owner=c.c_void_p();dacl=c.c_void_p();descriptor=c.c_void_p()
        error=adv.GetNamedSecurityInfoW(str(path.absolute()),1,5,c.byref(owner),None,
                                      c.byref(dacl),None,c.byref(descriptor))
        if error:raise OSError(error,'Windows ACL read failed')
        try:
            sid=_current_sid()
            trusted={sid,'S-1-5-18','S-1-5-32-544'}
            if _sid_text(owner) not in trusted or not dacl:return False
            control=w.WORD();revision=w.DWORD()
            if not adv.GetSecurityDescriptorControl(descriptor,c.byref(control),c.byref(revision)):
                return False
            if not control.value&0x1000 and not private_path(path.parent):return False
            # ACL header: revision, reserved, size, ACE count, reserved.
            count=c.cast(dacl,c.POINTER(w.WORD))[2]
            if not 1<=count<=1024:return False
            owner_allowed=False
            for number in range(count):
                ace=c.c_void_p()
                if not adv.GetAce(dacl,number,c.byref(ace)):return False
                kind=c.cast(ace,c.POINTER(w.BYTE))[0]
                if kind==1:continue  # deny ACE never grants another user access
                if kind!=0:return False  # no unknown/object/callback allow ACE
                identity=_sid_text(ace.value+8)
                if identity not in trusted:return False
                owner_allowed |= identity==sid
            return owner_allowed
        finally:kernel.LocalFree(descriptor)
    except (OSError,ValueError,TypeError):return False


def protect_private_path(path):
    """Protect a newly created provider file/directory before writing secrets."""
    path=Path(path)
    if not _ordinary(path):raise ValueError('private path must not be a reparse point or special file')
    if os.name!='nt':
        os.chmod(path,0o700 if path.is_dir() else 0o600)
        return
    c,w,adv,kernel=_windows_api()
    descriptor=c.c_void_p();dacl=c.c_void_p();owner=c.c_void_p()
    flags='OICI' if path.is_dir() else ''
    sid=_current_sid()
    sddl=f'O:{sid}D:P(A;{flags};FA;;;{sid})'
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,1,c.byref(descriptor),None):
        raise OSError('Windows private ACL construction failed')
    try:
        present=w.BOOL();defaulted=w.BOOL()
        if not adv.GetSecurityDescriptorDacl(descriptor,c.byref(present),c.byref(dacl),c.byref(defaulted)) or not present:
            raise OSError('Windows private DACL unavailable')
        if not adv.GetSecurityDescriptorOwner(descriptor,c.byref(owner),c.byref(defaulted)):
            raise OSError('Windows private owner unavailable')
        error=adv.SetNamedSecurityInfoW(str(path.absolute()),1,0x80000005,owner,None,dacl,None)
        if error:raise OSError(error,'Windows private ACL update failed')
    finally:kernel.LocalFree(descriptor)
    if not private_path(path):raise OSError('Windows private ACL verification failed')
