"""Fixed child bootstrap, copied alone; never imported with candidate code on host."""
import ctypes
import errno
import json
import os
import resource
import runpy
import sys


def main():
    mode, target, result_fd, notice_fd, cpu, memory, output = sys.argv[1:]
    # Set hard ceilings before loading any problem/analysis code.
    resource.setrlimit(resource.RLIMIT_CPU, (int(cpu), int(cpu)))
    resource.setrlimit(resource.RLIMIT_AS, (int(memory), int(memory)))
    resource.setrlimit(resource.RLIMIT_FSIZE, (int(output), int(output)))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    try:
        sec = ctypes.CDLL("libseccomp.so.2", use_errno=True)
        sec.seccomp_init.argtypes = [ctypes.c_uint32]
        sec.seccomp_init.restype = ctypes.c_void_p
        sec.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
        sec.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
        sec.seccomp_load.argtypes = [ctypes.c_void_p]
        sec.seccomp_release.argtypes = [ctypes.c_void_p]
        ctx = sec.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
        if not ctx:
            raise RuntimeError()
        try:
            for name in (
                "fork", "vfork", "clone", "clone3", "execve", "execveat",
                "socket", "socketpair", "ptrace", "process_vm_readv", "process_vm_writev",
                "mount", "umount2", "pivot_root", "chroot", "unshare", "setns",
                "setrlimit", "prlimit64", "bpf", "userfaultfd",
            ):
                syscall = sec.seccomp_syscall_resolve_name(name.encode())
                if syscall >= 0 and sec.seccomp_rule_add(ctx, 0x00050000 | errno.EPERM, syscall, 0):
                    raise RuntimeError()
            if sec.seccomp_load(ctx):
                raise RuntimeError()
        finally:
            sec.seccomp_release(ctx)
    except Exception:
        os._exit(78)  # no target has been imported/executed

    sys.path[:0] = ["/runtime", "/subject", "/deps"]
    os.environ["SCION_OBSERVATION_RESULT_FD"] = result_fd
    # One operational fact, closed before target code. No child-authored status
    # object or receipt is accepted by the host.
    os.write(int(notice_fd), b"\x01")
    os.close(int(notice_fd))
    if mode == "analysis":
        runpy.run_path("/input/analysis.py", run_name="__main__")
    else:
        runpy.run_module(target, run_name="__main__")


if __name__ == "__main__":
    main()
