#define _GNU_SOURCE
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#ifndef __linux__
#error "Scion trusted spawn requires Linux"
#endif

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/magic.h>
#include <linux/sched.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#if !defined(SYS_clone3) || !defined(SYS_close_range) || \
    !defined(SYS_pidfd_send_signal)
#error "Scion trusted spawn requires clone3, close_range, and pidfd syscalls"
#endif

#ifndef CLONE_INTO_CGROUP
#error "Scion trusted spawn requires CLONE_INTO_CGROUP headers"
#endif

#ifndef CLONE_ARGS_SIZE_VER2
#error "Scion trusted spawn requires clone_args ABI version 2 headers"
#endif

_Static_assert(CLONE_ARGS_SIZE_VER2 == 88, "unexpected clone_args v2 size");
_Static_assert(sizeof(struct clone_args) >= CLONE_ARGS_SIZE_VER2,
               "clone_args headers are older than ABI version 2");

#ifndef P_PIDFD
#define P_PIDFD ((idtype_t)3)
#endif

#define SCION_CLONE_FLAGS ((uint64_t)CLONE_INTO_CGROUP | (uint64_t)CLONE_PIDFD)
#define SCION_RELEASE_BYTE ((unsigned char)0x01)
#define SCION_ERROR_RECORD_SIZE 12
#define SCION_ERROR_RECORD_VERSION 1
#define SCION_HIGH_FD_MIN 64

enum ScionChildStage {
    SCION_STAGE_DUP_EXEC_ERROR = 1,
    SCION_STAGE_DUP_STDIN = 2,
    SCION_STAGE_DUP_STDOUT = 3,
    SCION_STAGE_DUP_STDERR = 4,
    SCION_STAGE_DUP_RELEASE = 5,
    SCION_STAGE_CLOSE_RANGE = 6,
    SCION_STAGE_SIGNAL_DISPOSITIONS = 7,
    SCION_STAGE_SIGNAL_MASK = 8,
    SCION_STAGE_RELEASE_READ = 9,
    SCION_STAGE_RELEASE_BYTE = 10,
    SCION_STAGE_RELEASE_CLOSE = 11,
    SCION_STAGE_CHDIR = 12,
    SCION_STAGE_EXECVE = 13,
};

enum ScionHandleState {
    SCION_HANDLE_BLOCKED = 1,
    SCION_HANDLE_RELEASED = 2,
    SCION_HANDLE_POISONED = 3,
    SCION_HANDLE_REAPED = 4,
};

typedef struct {
    PyObject_HEAD
    pid_t creator_pid;
    pid_t pid;
    int pidfd;
    int release_fd;
    int stdout_fd;
    int stderr_fd;
    int exec_error_fd;
    int state;
    int captures_taken;
    int terminal_cached;
    pid_t terminal_pid;
    uid_t terminal_uid;
    int terminal_code;
    int terminal_status;
} ScionBlockedChild;

typedef struct {
    char *executable;
    char **argv;
    Py_ssize_t argc;
    char **envp;
    Py_ssize_t envc;
    char *cwd;
    int cgroup_fd;
    int child_stdin_fd;
    int child_stdout_fd;
    int child_stderr_fd;
    int child_release_fd;
    int child_exec_error_fd;
    int parent_stdout_fd;
    int parent_stderr_fd;
    int parent_release_fd;
    int parent_exec_error_fd;
    sigset_t catchable_signals;
} ScionPreparedSpawn;

static PyTypeObject ScionBlockedChildType;

static void
scion_close_owned(int *fd)
{
    int value = *fd;
    *fd = -1;
    if (value >= 0) {
        (void)close(value);
    }
}

static int
scion_close_checked(int *fd)
{
    int value = *fd;
    int result;

    *fd = -1;
    if (value < 0) {
        return 0;
    }
    result = close(value);
    return result;
}

static void
scion_prepared_init(ScionPreparedSpawn *prepared)
{
    memset(prepared, 0, sizeof(*prepared));
    prepared->cgroup_fd = -1;
    prepared->child_stdin_fd = -1;
    prepared->child_stdout_fd = -1;
    prepared->child_stderr_fd = -1;
    prepared->child_release_fd = -1;
    prepared->child_exec_error_fd = -1;
    prepared->parent_stdout_fd = -1;
    prepared->parent_stderr_fd = -1;
    prepared->parent_release_fd = -1;
    prepared->parent_exec_error_fd = -1;
}

static void
scion_free_vector(char **items, Py_ssize_t count)
{
    Py_ssize_t index;

    if (items == NULL) {
        return;
    }
    for (index = 0; index < count; index++) {
        free(items[index]);
    }
    free(items);
}

static void
scion_prepared_cleanup(ScionPreparedSpawn *prepared)
{
    free(prepared->executable);
    prepared->executable = NULL;
    scion_free_vector(prepared->argv, prepared->argc);
    prepared->argv = NULL;
    scion_free_vector(prepared->envp, prepared->envc);
    prepared->envp = NULL;
    free(prepared->cwd);
    prepared->cwd = NULL;

    scion_close_owned(&prepared->cgroup_fd);
    scion_close_owned(&prepared->child_stdin_fd);
    scion_close_owned(&prepared->child_stdout_fd);
    scion_close_owned(&prepared->child_stderr_fd);
    scion_close_owned(&prepared->child_release_fd);
    scion_close_owned(&prepared->child_exec_error_fd);
    scion_close_owned(&prepared->parent_stdout_fd);
    scion_close_owned(&prepared->parent_stderr_fd);
    scion_close_owned(&prepared->parent_release_fd);
    scion_close_owned(&prepared->parent_exec_error_fd);
}

static int
scion_copy_bytes(PyObject *value, const char *label, char **destination)
{
    char *source;
    Py_ssize_t length;
    char *copy;

    if (!PyBytes_CheckExact(value)) {
        PyErr_Format(PyExc_TypeError, "%s must be exact bytes", label);
        return -1;
    }
    if (PyBytes_AsStringAndSize(value, &source, &length) < 0) {
        return -1;
    }
    if (length <= 0) {
        PyErr_Format(PyExc_ValueError, "%s must not be empty", label);
        return -1;
    }
    if (memchr(source, '\0', (size_t)length) != NULL) {
        PyErr_Format(PyExc_ValueError, "%s contains NUL", label);
        return -1;
    }
    if ((size_t)length == SIZE_MAX) {
        PyErr_NoMemory();
        return -1;
    }
    copy = malloc((size_t)length + 1U);
    if (copy == NULL) {
        PyErr_NoMemory();
        return -1;
    }
    memcpy(copy, source, (size_t)length);
    copy[length] = '\0';
    *destination = copy;
    return 0;
}

static int
scion_copy_vector(
    PyObject *tuple,
    const char *label,
    int require_nonempty,
    char ***destination,
    Py_ssize_t *destination_count)
{
    Py_ssize_t count;
    Py_ssize_t index;
    char **items;

    if (!PyTuple_CheckExact(tuple)) {
        PyErr_Format(PyExc_TypeError, "%s must be an exact tuple of bytes", label);
        return -1;
    }
    count = PyTuple_GET_SIZE(tuple);
    if (require_nonempty && count == 0) {
        PyErr_Format(PyExc_ValueError, "%s must not be empty", label);
        return -1;
    }
    if ((size_t)count > (SIZE_MAX / sizeof(char *)) - 1U) {
        PyErr_NoMemory();
        return -1;
    }
    items = calloc((size_t)count + 1U, sizeof(char *));
    if (items == NULL) {
        PyErr_NoMemory();
        return -1;
    }
    for (index = 0; index < count; index++) {
        char item_label[64];
        int written = snprintf(
            item_label, sizeof(item_label), "%s[%zd]", label, index);
        if (written < 0 || (size_t)written >= sizeof(item_label)) {
            PyErr_SetString(PyExc_RuntimeError, "vector label overflow");
            scion_free_vector(items, count);
            return -1;
        }
        if (scion_copy_bytes(PyTuple_GET_ITEM(tuple, index), item_label,
                             &items[index]) < 0) {
            scion_free_vector(items, count);
            return -1;
        }
    }
    *destination = items;
    *destination_count = count;
    return 0;
}

static int
scion_validate_environment(char **envp, Py_ssize_t envc)
{
    Py_ssize_t index;
    Py_ssize_t other;

    for (index = 0; index < envc; index++) {
        char *equals = strchr(envp[index], '=');
        size_t name_length;
        if (equals == NULL || equals == envp[index]) {
            PyErr_Format(
                PyExc_ValueError,
                "env[%zd] must be NAME=VALUE with a nonempty name",
                index);
            return -1;
        }
        name_length = (size_t)(equals - envp[index]);
        for (other = 0; other < index; other++) {
            char *other_equals = strchr(envp[other], '=');
            size_t other_length = (size_t)(other_equals - envp[other]);
            if (name_length == other_length &&
                memcmp(envp[index], envp[other], name_length) == 0) {
                PyErr_Format(PyExc_ValueError,
                             "env[%zd] duplicates an earlier name", index);
                return -1;
            }
        }
    }
    return 0;
}

static int
scion_duplicate_high(int fd)
{
    int duplicated = fcntl(fd, F_DUPFD_CLOEXEC, SCION_HIGH_FD_MIN);
    if (duplicated < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
    }
    return duplicated;
}

static int
scion_set_nonblocking(int fd)
{
    int flags = fcntl(fd, F_GETFL);
    if (flags < 0 || fcntl(fd, F_SETFL, flags | O_NONBLOCK) < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return -1;
    }
    return 0;
}

static int
scion_prepare_pipe(
    int *parent_end,
    int *child_end,
    int parent_reads)
{
    int pipe_fds[2] = {-1, -1};
    int child_original;

    if (pipe2(pipe_fds, O_CLOEXEC) < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return -1;
    }
    child_original = parent_reads ? pipe_fds[1] : pipe_fds[0];
    *parent_end = parent_reads ? pipe_fds[0] : pipe_fds[1];
    *child_end = scion_duplicate_high(child_original);
    if (*child_end < 0) {
        scion_close_owned(&pipe_fds[0]);
        scion_close_owned(&pipe_fds[1]);
        *parent_end = -1;
        return -1;
    }
    if (parent_reads) {
        pipe_fds[0] = -1;
    } else {
        pipe_fds[1] = -1;
    }
    scion_close_owned(&child_original);
    if (parent_reads) {
        pipe_fds[1] = -1;
        if (scion_set_nonblocking(*parent_end) < 0) {
            scion_close_owned(parent_end);
            scion_close_owned(child_end);
            return -1;
        }
    } else {
        pipe_fds[0] = -1;
    }
    return 0;
}

static int
scion_prepare_release_socket(int *parent_end, int *child_end)
{
    int sockets[2] = {-1, -1};

    if (socketpair(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0, sockets) < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return -1;
    }
    *parent_end = sockets[0];
    sockets[0] = -1;
    *child_end = scion_duplicate_high(sockets[1]);
    if (*child_end < 0) {
        scion_close_owned(parent_end);
        scion_close_owned(&sockets[1]);
        return -1;
    }
    scion_close_owned(&sockets[1]);
    return 0;
}

static int
scion_require_cloexec(int fd)
{
    int flags = fcntl(fd, F_GETFD);

    if (flags < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return -1;
    }
    if ((flags & FD_CLOEXEC) == 0) {
        PyErr_SetString(PyExc_RuntimeError,
                        "native-owned FD is missing FD_CLOEXEC");
        return -1;
    }
    return 0;
}

static int
scion_collect_catchable_signals(sigset_t *signals)
{
    int signal_number;

    if (sigemptyset(signals) < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return -1;
    }
    for (signal_number = 1; signal_number < NSIG; signal_number++) {
        struct sigaction action;

        if (signal_number == SIGKILL || signal_number == SIGSTOP) {
            continue;
        }
        errno = 0;
        if (sigaction(signal_number, NULL, &action) < 0) {
            if (errno == EINVAL) {
                continue;
            }
            PyErr_SetFromErrno(PyExc_OSError);
            return -1;
        }
        if (sigaddset(signals, signal_number) < 0) {
            PyErr_SetFromErrno(PyExc_OSError);
            return -1;
        }
    }
    return 0;
}

static int
scion_require_single_thread(void)
{
    DIR *directory;
    struct dirent *entry;
    int task_count = 0;
    int saved_errno = 0;

    directory = opendir("/proc/self/task");
    if (directory == NULL) {
        PyErr_SetFromErrnoWithFilename(PyExc_OSError, "/proc/self/task");
        return -1;
    }
    errno = 0;
    while ((entry = readdir(directory)) != NULL) {
        const unsigned char *cursor = (const unsigned char *)entry->d_name;
        int numeric = (*cursor != '\0');
        while (*cursor != '\0') {
            if (*cursor < (unsigned char)'0' || *cursor > (unsigned char)'9') {
                numeric = 0;
                break;
            }
            cursor++;
        }
        if (numeric) {
            task_count++;
        }
    }
    saved_errno = errno;
    if (closedir(directory) < 0 && saved_errno == 0) {
        saved_errno = errno;
    }
    if (saved_errno != 0) {
        errno = saved_errno;
        PyErr_SetFromErrnoWithFilename(PyExc_OSError, "/proc/self/task");
        return -1;
    }
    if (task_count != 1) {
        PyErr_Format(PyExc_RuntimeError,
                     "trusted spawn requires exactly one process task; found %d",
                     task_count);
        return -1;
    }
    return 0;
}

static int
scion_require_reapable_sigchld(void)
{
    struct sigaction action;

    if (sigaction(SIGCHLD, NULL, &action) < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return -1;
    }
    if (action.sa_handler != SIG_DFL ||
        (action.sa_flags & SA_NOCLDWAIT) != 0) {
        PyErr_SetString(
            PyExc_RuntimeError,
            "trusted spawn requires SIGCHLD exactly SIG_DFL without "
            "SA_NOCLDWAIT");
        return -1;
    }
    return 0;
}

static int
scion_prepare_cgroup_fd(int supplied_fd, int *prepared_fd)
{
    struct stat status;
    struct statfs filesystem;
    int duplicate;

    if (supplied_fd < 0) {
        PyErr_SetString(PyExc_ValueError, "cgroup_fd must be nonnegative");
        return -1;
    }
    duplicate = scion_duplicate_high(supplied_fd);
    if (duplicate < 0) {
        return -1;
    }
    if (fstat(duplicate, &status) < 0 || fstatfs(duplicate, &filesystem) < 0) {
        int saved_errno = errno;
        scion_close_owned(&duplicate);
        errno = saved_errno;
        PyErr_SetFromErrno(PyExc_OSError);
        return -1;
    }
    if (!S_ISDIR(status.st_mode) ||
        (unsigned long)filesystem.f_type != (unsigned long)CGROUP2_SUPER_MAGIC) {
        scion_close_owned(&duplicate);
        PyErr_SetString(PyExc_ValueError,
                        "cgroup_fd must name a cgroup-v2 directory");
        return -1;
    }
    *prepared_fd = duplicate;
    return 0;
}

static int
scion_prepare_spawn(
    ScionPreparedSpawn *prepared,
    int cgroup_fd,
    PyObject *executable,
    PyObject *argv,
    PyObject *env,
    PyObject *cwd)
{
    int dev_null = -1;
    struct stat null_status;

    if (scion_copy_bytes(executable, "executable", &prepared->executable) < 0 ||
        scion_copy_vector(argv, "argv", 1, &prepared->argv,
                          &prepared->argc) < 0 ||
        scion_copy_vector(env, "env", 0, &prepared->envp,
                          &prepared->envc) < 0 ||
        scion_copy_bytes(cwd, "cwd", &prepared->cwd) < 0) {
        return -1;
    }
    if (prepared->executable[0] != '/' || prepared->cwd[0] != '/') {
        PyErr_SetString(PyExc_ValueError,
                        "executable and cwd must be absolute byte paths");
        return -1;
    }
    if (strcmp(prepared->executable, prepared->argv[0]) != 0) {
        PyErr_SetString(PyExc_ValueError,
                        "argv[0] must exactly equal executable");
        return -1;
    }
    if (scion_validate_environment(prepared->envp, prepared->envc) < 0 ||
        scion_prepare_cgroup_fd(cgroup_fd, &prepared->cgroup_fd) < 0) {
        return -1;
    }

    dev_null = open("/dev/null", O_RDONLY | O_CLOEXEC | O_NOCTTY);
    if (dev_null < 0) {
        PyErr_SetFromErrnoWithFilename(PyExc_OSError, "/dev/null");
        return -1;
    }
    if (fstat(dev_null, &null_status) < 0) {
        int saved_errno = errno;
        scion_close_owned(&dev_null);
        errno = saved_errno;
        PyErr_SetFromErrnoWithFilename(PyExc_OSError, "/dev/null");
        return -1;
    }
    if (!S_ISCHR(null_status.st_mode) || major(null_status.st_rdev) != 1U ||
        minor(null_status.st_rdev) != 3U) {
        scion_close_owned(&dev_null);
        errno = ENODEV;
        PyErr_SetFromErrnoWithFilename(PyExc_OSError, "/dev/null");
        return -1;
    }
    prepared->child_stdin_fd = scion_duplicate_high(dev_null);
    scion_close_owned(&dev_null);
    if (prepared->child_stdin_fd < 0 ||
        scion_prepare_pipe(&prepared->parent_stdout_fd,
                           &prepared->child_stdout_fd, 1) < 0 ||
        scion_prepare_pipe(&prepared->parent_stderr_fd,
                           &prepared->child_stderr_fd, 1) < 0 ||
        scion_prepare_release_socket(&prepared->parent_release_fd,
                                     &prepared->child_release_fd) < 0 ||
        scion_prepare_pipe(&prepared->parent_exec_error_fd,
                           &prepared->child_exec_error_fd, 1) < 0) {
        return -1;
    }
    if (scion_require_cloexec(prepared->cgroup_fd) < 0 ||
        scion_require_cloexec(prepared->child_stdin_fd) < 0 ||
        scion_require_cloexec(prepared->child_stdout_fd) < 0 ||
        scion_require_cloexec(prepared->child_stderr_fd) < 0 ||
        scion_require_cloexec(prepared->child_release_fd) < 0 ||
        scion_require_cloexec(prepared->child_exec_error_fd) < 0 ||
        scion_require_cloexec(prepared->parent_stdout_fd) < 0 ||
        scion_require_cloexec(prepared->parent_stderr_fd) < 0 ||
        scion_require_cloexec(prepared->parent_release_fd) < 0 ||
        scion_require_cloexec(prepared->parent_exec_error_fd) < 0 ||
        scion_collect_catchable_signals(&prepared->catchable_signals) < 0 ||
        scion_require_single_thread() < 0) {
        return -1;
    }
    return scion_require_reapable_sigchld();
}

static void
scion_child_write_error(int fd, unsigned char stage, int error_number)
{
    unsigned char record[SCION_ERROR_RECORD_SIZE];
    size_t written = 0;
    uint32_t encoded_error;

    if (error_number <= 0) {
        error_number = EIO;
    }
    encoded_error = (uint32_t)error_number;
    record[0] = (unsigned char)'S';
    record[1] = (unsigned char)'C';
    record[2] = (unsigned char)'X';
    record[3] = (unsigned char)'E';
    record[4] = SCION_ERROR_RECORD_VERSION;
    record[5] = stage;
    record[6] = 0;
    record[7] = 0;
    record[8] = (unsigned char)(encoded_error & 0xffU);
    record[9] = (unsigned char)((encoded_error >> 8) & 0xffU);
    record[10] = (unsigned char)((encoded_error >> 16) & 0xffU);
    record[11] = (unsigned char)((encoded_error >> 24) & 0xffU);

    while (written < sizeof(record)) {
        ssize_t result = write(fd, record + written, sizeof(record) - written);
        if (result > 0) {
            written += (size_t)result;
            continue;
        }
        if (result < 0 && errno == EINTR) {
            continue;
        }
        break;
    }
}

static void
scion_child_fail(int reporter_fd, unsigned char stage, int error_number)
{
    scion_child_write_error(reporter_fd, stage, error_number);
    _exit(127);
}

static int
scion_child_reset_dispositions(const sigset_t *catchable_signals)
{
    int signal_number;
    struct sigaction action;

    memset(&action, 0, sizeof(action));
    action.sa_handler = SIG_DFL;
    if (sigemptyset(&action.sa_mask) < 0) {
        return -1;
    }
    for (signal_number = 1; signal_number < NSIG; signal_number++) {
        int member = sigismember(catchable_signals, signal_number);
        if (member < 0) {
            return -1;
        }
        if (member == 1 && sigaction(signal_number, &action, NULL) < 0) {
            return -1;
        }
    }
    return 0;
}

static void
scion_child_exec(const ScionPreparedSpawn *prepared)
{
    unsigned char release_byte = 0;
    ssize_t release_result;
    sigset_t empty_mask;

    if (dup3(prepared->child_exec_error_fd, 4, O_CLOEXEC) < 0) {
        scion_child_fail(prepared->child_exec_error_fd,
                         SCION_STAGE_DUP_EXEC_ERROR, errno);
    }
    if (dup3(prepared->child_stdin_fd, 0, 0) < 0) {
        scion_child_fail(4, SCION_STAGE_DUP_STDIN, errno);
    }
    if (dup3(prepared->child_stdout_fd, 1, 0) < 0) {
        scion_child_fail(4, SCION_STAGE_DUP_STDOUT, errno);
    }
    if (dup3(prepared->child_stderr_fd, 2, 0) < 0) {
        scion_child_fail(4, SCION_STAGE_DUP_STDERR, errno);
    }
    if (dup3(prepared->child_release_fd, 3, O_CLOEXEC) < 0) {
        scion_child_fail(4, SCION_STAGE_DUP_RELEASE, errno);
    }
    if (syscall(SYS_close_range, 5U, UINT_MAX, 0U) < 0) {
        scion_child_fail(4, SCION_STAGE_CLOSE_RANGE, errno);
    }
    if (scion_child_reset_dispositions(&prepared->catchable_signals) < 0) {
        scion_child_fail(4, SCION_STAGE_SIGNAL_DISPOSITIONS, errno);
    }
    if (sigemptyset(&empty_mask) < 0 ||
        sigprocmask(SIG_SETMASK, &empty_mask, NULL) < 0) {
        scion_child_fail(4, SCION_STAGE_SIGNAL_MASK, errno);
    }

    do {
        release_result = read(3, &release_byte, 1U);
    } while (release_result < 0 && errno == EINTR);
    if (release_result != 1) {
        scion_child_fail(4, SCION_STAGE_RELEASE_READ,
                         release_result == 0 ? EPIPE : errno);
    }
    if (release_byte != SCION_RELEASE_BYTE) {
        scion_child_fail(4, SCION_STAGE_RELEASE_BYTE, EPROTO);
    }
    if (close(3) < 0) {
        scion_child_fail(4, SCION_STAGE_RELEASE_CLOSE, errno);
    }
    if (chdir(prepared->cwd) < 0) {
        scion_child_fail(4, SCION_STAGE_CHDIR, errno);
    }
    execve(prepared->executable, prepared->argv, prepared->envp);
    scion_child_fail(4, SCION_STAGE_EXECVE, errno);
}

static int
scion_cache_terminal(ScionBlockedChild *self, const siginfo_t *info)
{
    if (info->si_pid != self->pid) {
        PyErr_SetString(PyExc_RuntimeError,
                        "pidfd wait returned a different process identity");
        return -1;
    }
    if (info->si_code != CLD_EXITED && info->si_code != CLD_KILLED &&
        info->si_code != CLD_DUMPED) {
        PyErr_Format(PyExc_RuntimeError,
                     "pidfd wait returned unsupported si_code %d",
                     info->si_code);
        return -1;
    }
    if (self->terminal_cached &&
        (self->terminal_pid != info->si_pid ||
         self->terminal_uid != info->si_uid ||
         self->terminal_code != info->si_code ||
         self->terminal_status != info->si_status)) {
        PyErr_SetString(PyExc_RuntimeError,
                        "pidfd terminal observation changed before reap");
        return -1;
    }
    self->terminal_pid = info->si_pid;
    self->terminal_uid = info->si_uid;
    self->terminal_code = info->si_code;
    self->terminal_status = info->si_status;
    self->terminal_cached = 1;
    return 0;
}

static int
scion_terminal_matches_cache(
    const ScionBlockedChild *self,
    const siginfo_t *info)
{
    return self->terminal_cached &&
           self->terminal_pid == info->si_pid &&
           self->terminal_uid == info->si_uid &&
           self->terminal_code == info->si_code &&
           self->terminal_status == info->si_status;
}

static int
scion_terminal_info_matches(const siginfo_t *left, const siginfo_t *right)
{
    return left->si_pid == right->si_pid &&
           left->si_uid == right->si_uid &&
           left->si_code == right->si_code &&
           left->si_status == right->si_status;
}

static PyObject *
scion_terminal_tuple(const ScionBlockedChild *self)
{
    int wait_status;
    int return_code;
    int signal_number;
    int core_dumped;
    PyObject *result;

    if (self->terminal_code == CLD_EXITED) {
        wait_status = (self->terminal_status & 0xff) << 8;
        return_code = self->terminal_status & 0xff;
        signal_number = 0;
        core_dumped = 0;
    } else {
        signal_number = self->terminal_status & 0x7f;
        core_dumped = self->terminal_code == CLD_DUMPED;
        wait_status = signal_number | (core_dumped ? 0x80 : 0);
        return_code = -signal_number;
    }

    result = PyTuple_New(8);
    if (result == NULL) {
        return NULL;
    }
#define SCION_SET_TUPLE_LONG(position, value)                                  \
    do {                                                                       \
        PyObject *item = PyLong_FromLong((long)(value));                       \
        if (item == NULL) {                                                     \
            Py_DECREF(result);                                                  \
            return NULL;                                                        \
        }                                                                       \
        PyTuple_SET_ITEM(result, (position), item);                             \
    } while (0)
    SCION_SET_TUPLE_LONG(0, self->terminal_pid);
    SCION_SET_TUPLE_LONG(1, self->terminal_uid);
    SCION_SET_TUPLE_LONG(2, self->terminal_code);
    SCION_SET_TUPLE_LONG(3, self->terminal_status);
    SCION_SET_TUPLE_LONG(4, wait_status);
    SCION_SET_TUPLE_LONG(5, return_code);
    SCION_SET_TUPLE_LONG(6, signal_number);
    SCION_SET_TUPLE_LONG(7, core_dumped);
#undef SCION_SET_TUPLE_LONG
    return result;
}

static int
scion_waitid_pidfd(int pidfd, int options, siginfo_t *info)
{
    int result;
    do {
        memset(info, 0, sizeof(*info));
        result = waitid(P_PIDFD, (id_t)pidfd, info, options);
    } while (result < 0 && errno == EINTR);
    return result;
}

static int
scion_require_handle_authority(ScionBlockedChild *self)
{
    if (getpid() != self->creator_pid) {
        PyErr_SetString(PyExc_RuntimeError,
                        "BlockedChild authority belongs to its creator PID");
        return -1;
    }
    if (scion_require_single_thread() < 0 ||
        scion_require_reapable_sigchld() < 0) {
        return -1;
    }
    return 0;
}

static void
scion_close_handle_fds(ScionBlockedChild *self)
{
    scion_close_owned(&self->release_fd);
    scion_close_owned(&self->stdout_fd);
    scion_close_owned(&self->stderr_fd);
    scion_close_owned(&self->exec_error_fd);
    scion_close_owned(&self->pidfd);
}

static void
scion_destructor_abort(void)
{
    abort();
}

static void
scion_settle_blocked_destructor(ScionBlockedChild *self)
{
    siginfo_t observed;
    siginfo_t reaped;
    int terminal_observed = 0;
    int signal_result;
    int signal_errno;

    if (scion_close_checked(&self->release_fd) < 0 || self->pidfd < 0) {
        scion_destructor_abort();
    }
    if (scion_waitid_pidfd(self->pidfd,
                           WEXITED | WNOWAIT | WNOHANG, &observed) < 0) {
        scion_destructor_abort();
    }
    if (observed.si_pid != 0 && observed.si_pid != self->pid) {
        scion_destructor_abort();
    }
    terminal_observed = observed.si_pid == self->pid;
    if (observed.si_pid == 0) {
        signal_result = (int)syscall(SYS_pidfd_send_signal, self->pidfd,
                                     SIGKILL, NULL, 0U);
        signal_errno = errno;
        if (signal_result < 0) {
            if (signal_errno != ESRCH ||
                scion_waitid_pidfd(self->pidfd,
                                   WEXITED | WNOWAIT | WNOHANG,
                                   &observed) < 0 ||
                observed.si_pid != self->pid) {
                scion_destructor_abort();
            }
            terminal_observed = 1;
        }
    }
    if (scion_waitid_pidfd(self->pidfd, WEXITED, &reaped) < 0 ||
        reaped.si_pid != self->pid ||
        (terminal_observed &&
         !scion_terminal_info_matches(&observed, &reaped))) {
        scion_destructor_abort();
    }
    self->state = SCION_HANDLE_REAPED;
}

static void
ScionBlockedChild_dealloc(ScionBlockedChild *self)
{
    if (getpid() != self->creator_pid) {
        scion_close_handle_fds(self);
        PyObject_Del(self);
        return;
    }
    if (self->state == SCION_HANDLE_BLOCKED) {
        scion_settle_blocked_destructor(self);
    } else if (self->state == SCION_HANDLE_RELEASED ||
               self->state == SCION_HANDLE_POISONED) {
        scion_destructor_abort();
    } else if (self->state != SCION_HANDLE_REAPED) {
        scion_destructor_abort();
    }
    scion_close_handle_fds(self);
    PyObject_Del(self);
}

static PyObject *
ScionBlockedChild_release(ScionBlockedChild *self, PyObject *Py_UNUSED(ignored))
{
    unsigned char byte = SCION_RELEASE_BYTE;
    ssize_t result;
    int release_fd;
    int close_result;
    int saved_errno = 0;

    if (scion_require_handle_authority(self) < 0) {
        return NULL;
    }
    if (self->state != SCION_HANDLE_BLOCKED || self->release_fd < 0) {
        PyErr_SetString(PyExc_RuntimeError,
                        "blocked child release is exact one-shot");
        return NULL;
    }
    release_fd = self->release_fd;
    self->release_fd = -1;
    do {
        result = send(release_fd, &byte, 1U, MSG_NOSIGNAL);
    } while (result < 0 && errno == EINTR);
    if (result != 1) {
        saved_errno = result < 0 ? errno : EIO;
    }
    close_result = close(release_fd);
    if (close_result < 0 && saved_errno == 0) {
        saved_errno = errno;
    }
    if (saved_errno != 0) {
        self->state = SCION_HANDLE_POISONED;
        errno = saved_errno;
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    self->state = SCION_HANDLE_RELEASED;
    Py_RETURN_NONE;
}

static PyObject *
ScionBlockedChild_take_capture_fds(
    ScionBlockedChild *self,
    PyObject *Py_UNUSED(ignored))
{
    PyObject *result;

    if (scion_require_handle_authority(self) < 0) {
        return NULL;
    }
    if (self->state == SCION_HANDLE_REAPED || self->captures_taken ||
        self->stdout_fd < 0 || self->stderr_fd < 0 ||
        self->exec_error_fd < 0) {
        PyErr_SetString(PyExc_RuntimeError,
                        "capture FDs can be transferred exactly once");
        return NULL;
    }
    result = Py_BuildValue("(iii)", self->stdout_fd, self->stderr_fd,
                           self->exec_error_fd);
    if (result == NULL) {
        return NULL;
    }
    self->stdout_fd = -1;
    self->stderr_fd = -1;
    self->exec_error_fd = -1;
    self->captures_taken = 1;
    return result;
}

static PyObject *
ScionBlockedChild_dup_pidfd(
    ScionBlockedChild *self,
    PyObject *Py_UNUSED(ignored))
{
    int duplicate;

    if (scion_require_handle_authority(self) < 0) {
        return NULL;
    }
    if (self->pidfd < 0 || self->state == SCION_HANDLE_REAPED) {
        PyErr_SetString(PyExc_RuntimeError,
                        "pidfd cannot be duplicated after reap");
        return NULL;
    }
    duplicate = fcntl(self->pidfd, F_DUPFD_CLOEXEC, SCION_HIGH_FD_MIN);
    if (duplicate < 0) {
        return PyErr_SetFromErrno(PyExc_OSError);
    }
    {
        PyObject *result = PyLong_FromLong(duplicate);
        if (result == NULL) {
            scion_close_owned(&duplicate);
        }
        return result;
    }
}

static PyObject *
ScionBlockedChild_peek_wait(
    ScionBlockedChild *self,
    PyObject *Py_UNUSED(ignored))
{
    siginfo_t info;

    if (scion_require_handle_authority(self) < 0) {
        return NULL;
    }
    if (self->state == SCION_HANDLE_REAPED) {
        PyErr_SetString(PyExc_RuntimeError, "child was already reaped");
        return NULL;
    }
    if (!self->terminal_cached) {
        if (scion_waitid_pidfd(self->pidfd,
                               WEXITED | WNOWAIT | WNOHANG, &info) < 0) {
            return PyErr_SetFromErrno(PyExc_OSError);
        }
        if (info.si_pid == 0) {
            Py_RETURN_NONE;
        }
        if (scion_cache_terminal(self, &info) < 0) {
            return NULL;
        }
    }
    return scion_terminal_tuple(self);
}

static PyObject *
ScionBlockedChild_reap(ScionBlockedChild *self, PyObject *Py_UNUSED(ignored))
{
    siginfo_t info;
    PyObject *result;

    if (scion_require_handle_authority(self) < 0) {
        return NULL;
    }
    if (self->state == SCION_HANDLE_REAPED) {
        PyErr_SetString(PyExc_RuntimeError, "child reap is exact one-shot");
        return NULL;
    }
    if (!self->terminal_cached) {
        PyErr_SetString(
            PyExc_RuntimeError,
            "public reap requires a terminal fact cached by peek_wait");
        return NULL;
    }
    result = scion_terminal_tuple(self);
    if (result == NULL) {
        return NULL;
    }
    if (scion_waitid_pidfd(self->pidfd, WEXITED, &info) < 0) {
        Py_DECREF(result);
        return PyErr_SetFromErrno(PyExc_OSError);
    }
    if (!scion_terminal_matches_cache(self, &info)) {
        Py_DECREF(result);
        scion_destructor_abort();
    }
    self->state = SCION_HANDLE_REAPED;
    return result;
}

static PyObject *
ScionBlockedChild_send_signal(ScionBlockedChild *self, PyObject *argument)
{
    long signal_number;

    if (scion_require_handle_authority(self) < 0) {
        return NULL;
    }
    if (self->state == SCION_HANDLE_REAPED) {
        PyErr_SetString(PyExc_RuntimeError, "cannot signal a reaped child");
        return NULL;
    }
    if (!PyLong_CheckExact(argument)) {
        PyErr_SetString(PyExc_TypeError, "signal must be an exact int");
        return NULL;
    }
    signal_number = PyLong_AsLong(argument);
    if (signal_number == -1 && PyErr_Occurred()) {
        return NULL;
    }
    if (signal_number <= 0 || signal_number >= NSIG) {
        PyErr_SetString(PyExc_ValueError, "signal must be in 1..NSIG-1");
        return NULL;
    }
    if (syscall(SYS_pidfd_send_signal, self->pidfd, (int)signal_number,
                NULL, 0U) < 0) {
        return PyErr_SetFromErrno(PyExc_OSError);
    }
    Py_RETURN_NONE;
}

static PyObject *
ScionBlockedChild_get_pid(ScionBlockedChild *self, void *Py_UNUSED(context))
{
    return PyLong_FromLong((long)self->pid);
}

static PyObject *
ScionBlockedChild_get_state(ScionBlockedChild *self, void *Py_UNUSED(context))
{
    const char *state = "UNKNOWN";
    if (self->state == SCION_HANDLE_BLOCKED) {
        state = "BLOCKED";
    } else if (self->state == SCION_HANDLE_RELEASED) {
        state = "RELEASED";
    } else if (self->state == SCION_HANDLE_POISONED) {
        state = "POISONED";
    } else if (self->state == SCION_HANDLE_REAPED) {
        state = "REAPED";
    }
    return PyUnicode_FromString(state);
}

static PyObject *
ScionBlockedChild_reject_copy(
    ScionBlockedChild *Py_UNUSED(self),
    PyObject *Py_UNUSED(argument))
{
    PyErr_SetString(PyExc_TypeError,
                    "BlockedChild authority cannot be copied or pickled");
    return NULL;
}

static PyMethodDef ScionBlockedChild_methods[] = {
    {"release", (PyCFunction)ScionBlockedChild_release, METH_NOARGS,
     PyDoc_STR("Write the one exact release byte and close release authority.")},
    {"take_capture_fds", (PyCFunction)ScionBlockedChild_take_capture_fds,
     METH_NOARGS,
     PyDoc_STR("Transfer stdout, stderr, and exec-error reader FDs once.")},
    {"dup_pidfd", (PyCFunction)ScionBlockedChild_dup_pidfd, METH_NOARGS,
     PyDoc_STR("Return a close-on-exec duplicate pidfd for polling.")},
    {"peek_wait", (PyCFunction)ScionBlockedChild_peek_wait, METH_NOARGS,
     PyDoc_STR("Observe terminal identity through waitid(P_PIDFD, WNOWAIT).")},
    {"reap", (PyCFunction)ScionBlockedChild_reap, METH_NOARGS,
     PyDoc_STR("Reap exactly once through the same pidfd.")},
    {"send_signal", (PyCFunction)ScionBlockedChild_send_signal, METH_O,
     PyDoc_STR("Signal the leader through pidfd_send_signal.")},
    {"__copy__", (PyCFunction)ScionBlockedChild_reject_copy, METH_NOARGS,
     PyDoc_STR("Reject copying native authority.")},
    {"__deepcopy__", (PyCFunction)ScionBlockedChild_reject_copy, METH_O,
     PyDoc_STR("Reject deep-copying native authority.")},
    {"__reduce__", (PyCFunction)ScionBlockedChild_reject_copy, METH_NOARGS,
     PyDoc_STR("Reject pickling native authority.")},
    {"__reduce_ex__", (PyCFunction)ScionBlockedChild_reject_copy, METH_O,
     PyDoc_STR("Reject protocol-specific pickling native authority.")},
    {NULL, NULL, 0, NULL},
};

static PyGetSetDef ScionBlockedChild_getset[] = {
    {"pid", (getter)ScionBlockedChild_get_pid, NULL,
     PyDoc_STR("Kernel PID returned with the pidfd."), NULL},
    {"state", (getter)ScionBlockedChild_get_state, NULL,
     PyDoc_STR("Native one-shot state."), NULL},
    {NULL, NULL, NULL, NULL, NULL},
};

static PyTypeObject ScionBlockedChildType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "scion.runtime.native.BlockedChild",
    .tp_basicsize = sizeof(ScionBlockedChild),
    .tp_dealloc = (destructor)ScionBlockedChild_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_doc = PyDoc_STR("Unforgeable owner of one native blocked child."),
    .tp_methods = ScionBlockedChild_methods,
    .tp_getset = ScionBlockedChild_getset,
    .tp_new = NULL,
};

static PyObject *
scion_spawn_blocked(PyObject *Py_UNUSED(module), PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {
        "cgroup_fd", "executable", "argv", "env", "cwd", NULL};
    PyObject *cgroup_fd_object;
    long supplied_cgroup_fd_long;
    int supplied_cgroup_fd;
    PyObject *executable;
    PyObject *argv;
    PyObject *env;
    PyObject *cwd;
    ScionPreparedSpawn prepared;
    ScionBlockedChild *handle = NULL;
    struct clone_args clone_arguments;
    sigset_t previous_mask;
    int pidfd = -1;
    long clone_result;
    int close_errno = 0;
    int postclone_failed = 0;
    int mask_result;
    int clone_errno;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO!O!O!O!:spawn_blocked",
                                     keywords, &cgroup_fd_object,
                                     &PyBytes_Type, &executable,
                                     &PyTuple_Type, &argv,
                                     &PyTuple_Type, &env,
                                     &PyBytes_Type, &cwd)) {
        return NULL;
    }
    if (!PyLong_CheckExact(cgroup_fd_object)) {
        PyErr_SetString(PyExc_TypeError, "cgroup_fd must be an exact int");
        return NULL;
    }
    supplied_cgroup_fd_long = PyLong_AsLong(cgroup_fd_object);
    if ((supplied_cgroup_fd_long == -1 && PyErr_Occurred()) ||
        supplied_cgroup_fd_long < INT_MIN ||
        supplied_cgroup_fd_long > INT_MAX) {
        if (!PyErr_Occurred()) {
            PyErr_SetString(PyExc_OverflowError, "cgroup_fd is outside int range");
        }
        return NULL;
    }
    supplied_cgroup_fd = (int)supplied_cgroup_fd_long;
    scion_prepared_init(&prepared);
    if (scion_prepare_spawn(&prepared, supplied_cgroup_fd, executable, argv,
                            env, cwd) < 0) {
        scion_prepared_cleanup(&prepared);
        return NULL;
    }

    handle = PyObject_New(ScionBlockedChild, &ScionBlockedChildType);
    if (handle == NULL) {
        scion_prepared_cleanup(&prepared);
        return NULL;
    }
    handle->creator_pid = getpid();
    handle->pid = -1;
    handle->pidfd = -1;
    handle->release_fd = -1;
    handle->stdout_fd = -1;
    handle->stderr_fd = -1;
    handle->exec_error_fd = -1;
    /* The object is not armed until clone3 returns a leader and pidfd. */
    handle->state = SCION_HANDLE_REAPED;
    handle->captures_taken = 0;
    handle->terminal_cached = 0;
    handle->terminal_pid = -1;
    handle->terminal_uid = 0;
    handle->terminal_code = 0;
    handle->terminal_status = 0;

    memset(&clone_arguments, 0, sizeof(clone_arguments));
    clone_arguments.flags = SCION_CLONE_FLAGS;
    clone_arguments.pidfd = (uint64_t)(uintptr_t)&pidfd;
    clone_arguments.exit_signal = SIGCHLD;
    clone_arguments.cgroup = (__u64)(unsigned int)prepared.cgroup_fd;

    mask_result = pthread_sigmask(SIG_BLOCK, &prepared.catchable_signals,
                                  &previous_mask);
    if (mask_result != 0) {
        errno = mask_result;
        PyErr_SetFromErrno(PyExc_OSError);
        scion_prepared_cleanup(&prepared);
        Py_DECREF(handle);
        return NULL;
    }
    clone_result = syscall(SYS_clone3, &clone_arguments, CLONE_ARGS_SIZE_VER2);
    if (clone_result == 0) {
        scion_child_exec(&prepared);
    }
    clone_errno = errno;
    if (clone_result < 0) {
        mask_result = pthread_sigmask(SIG_SETMASK, &previous_mask, NULL);
        if (mask_result != 0) {
            scion_destructor_abort();
        }
        errno = clone_errno;
        PyErr_SetFromErrno(PyExc_OSError);
        scion_prepared_cleanup(&prepared);
        Py_DECREF(handle);
        return NULL;
    }

    handle->pid = (pid_t)clone_result;
    handle->pidfd = pidfd;
    handle->state = SCION_HANDLE_BLOCKED;
    handle->release_fd = prepared.parent_release_fd;
    prepared.parent_release_fd = -1;
    handle->stdout_fd = prepared.parent_stdout_fd;
    prepared.parent_stdout_fd = -1;
    handle->stderr_fd = prepared.parent_stderr_fd;
    prepared.parent_stderr_fd = -1;
    handle->exec_error_fd = prepared.parent_exec_error_fd;
    prepared.parent_exec_error_fd = -1;

    if (scion_require_cloexec(handle->pidfd) < 0) {
        postclone_failed = 1;
    }

#define SCION_PARENT_CLOSE_OR_REMEMBER(field)                                  \
    do {                                                                       \
        if (scion_close_checked(&(field)) < 0 && close_errno == 0) {           \
            close_errno = errno;                                               \
        }                                                                       \
    } while (0)
    SCION_PARENT_CLOSE_OR_REMEMBER(prepared.cgroup_fd);
    SCION_PARENT_CLOSE_OR_REMEMBER(prepared.child_stdin_fd);
    SCION_PARENT_CLOSE_OR_REMEMBER(prepared.child_stdout_fd);
    SCION_PARENT_CLOSE_OR_REMEMBER(prepared.child_stderr_fd);
    SCION_PARENT_CLOSE_OR_REMEMBER(prepared.child_release_fd);
    SCION_PARENT_CLOSE_OR_REMEMBER(prepared.child_exec_error_fd);
#undef SCION_PARENT_CLOSE_OR_REMEMBER

    if (close_errno != 0) {
        postclone_failed = 1;
        if (!PyErr_Occurred()) {
            errno = close_errno;
            PyErr_SetFromErrno(PyExc_OSError);
        }
    }
    scion_prepared_cleanup(&prepared);
    if (postclone_failed) {
        scion_settle_blocked_destructor(handle);
        mask_result = pthread_sigmask(SIG_SETMASK, &previous_mask, NULL);
        if (mask_result != 0) {
            scion_destructor_abort();
        }
        Py_DECREF(handle);
        return NULL;
    }
    mask_result = pthread_sigmask(SIG_SETMASK, &previous_mask, NULL);
    if (mask_result != 0) {
        scion_settle_blocked_destructor(handle);
        scion_destructor_abort();
    }
    return (PyObject *)handle;
}

static PyMethodDef module_methods[] = {
    {"spawn_blocked", (PyCFunction)(void (*)(void))scion_spawn_blocked,
     METH_VARARGS | METH_KEYWORDS,
     PyDoc_STR("Atomically clone one blocked child into an exact cgroup-v2 FD.")},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module_definition = {
    PyModuleDef_HEAD_INIT,
    .m_name = "_spawn_into_cgroup",
    .m_doc = "Minimal clone3(CLONE_INTO_CGROUP|CLONE_PIDFD) authority.",
    .m_size = -1,
    .m_methods = module_methods,
};

static int
scion_add_int_constant(PyObject *module, const char *name, long long value)
{
    PyObject *number = PyLong_FromLongLong(value);
    if (number == NULL || PyModule_AddObject(module, name, number) < 0) {
        Py_XDECREF(number);
        return -1;
    }
    return 0;
}

static int
scion_add_text_constant(PyObject *module, const char *name, const char *value)
{
    PyObject *text = PyUnicode_FromString(value);
    if (text == NULL || PyModule_AddObject(module, name, text) < 0) {
        Py_XDECREF(text);
        return -1;
    }
    return 0;
}

PyMODINIT_FUNC
PyInit__spawn_into_cgroup(void)
{
    PyObject *module;
    PyObject *magic;

    if (PyType_Ready(&ScionBlockedChildType) < 0) {
        return NULL;
    }
    module = PyModule_Create(&module_definition);
    if (module == NULL) {
        return NULL;
    }
    Py_INCREF(&ScionBlockedChildType);
    if (PyModule_AddObject(module, "BlockedChild",
                           (PyObject *)&ScionBlockedChildType) < 0) {
        Py_DECREF(&ScionBlockedChildType);
        Py_DECREF(module);
        return NULL;
    }

    if (scion_add_int_constant(module, "CLONE_FLAGS",
                               (long long)SCION_CLONE_FLAGS) < 0 ||
        scion_add_int_constant(module, "CLONE_ARGS_SIZE",
                               CLONE_ARGS_SIZE_VER2) < 0 ||
        scion_add_int_constant(module, "EXIT_SIGNAL", SIGCHLD) < 0 ||
        scion_add_int_constant(module, "CHILD_STDIN_FD", 0) < 0 ||
        scion_add_int_constant(module, "CHILD_STDOUT_FD", 1) < 0 ||
        scion_add_int_constant(module, "CHILD_STDERR_FD", 2) < 0 ||
        scion_add_int_constant(module, "CHILD_RELEASE_FD", 3) < 0 ||
        scion_add_int_constant(module, "CHILD_EXEC_ERROR_FD", 4) < 0 ||
        scion_add_int_constant(module, "RELEASE_BYTE", SCION_RELEASE_BYTE) < 0 ||
        scion_add_int_constant(module, "ERROR_RECORD_VERSION",
                               SCION_ERROR_RECORD_VERSION) < 0 ||
        scion_add_int_constant(module, "ERROR_RECORD_SIZE",
                               SCION_ERROR_RECORD_SIZE) < 0 ||
        scion_add_int_constant(module, "ERROR_STAGE_DUP_EXEC_ERROR",
                               SCION_STAGE_DUP_EXEC_ERROR) < 0 ||
        scion_add_int_constant(module, "ERROR_STAGE_DUP_STDIN",
                               SCION_STAGE_DUP_STDIN) < 0 ||
        scion_add_int_constant(module, "ERROR_STAGE_DUP_STDOUT",
                               SCION_STAGE_DUP_STDOUT) < 0 ||
        scion_add_int_constant(module, "ERROR_STAGE_DUP_STDERR",
                               SCION_STAGE_DUP_STDERR) < 0 ||
        scion_add_int_constant(module, "ERROR_STAGE_DUP_RELEASE",
                               SCION_STAGE_DUP_RELEASE) < 0 ||
        scion_add_int_constant(module, "ERROR_STAGE_CLOSE_RANGE",
                               SCION_STAGE_CLOSE_RANGE) < 0 ||
        scion_add_int_constant(module, "ERROR_STAGE_SIGNAL_DISPOSITIONS",
                               SCION_STAGE_SIGNAL_DISPOSITIONS) < 0 ||
        scion_add_int_constant(module, "ERROR_STAGE_SIGNAL_MASK",
                               SCION_STAGE_SIGNAL_MASK) < 0 ||
        scion_add_int_constant(module, "ERROR_STAGE_RELEASE_READ",
                               SCION_STAGE_RELEASE_READ) < 0 ||
        scion_add_int_constant(module, "ERROR_STAGE_RELEASE_BYTE",
                               SCION_STAGE_RELEASE_BYTE) < 0 ||
        scion_add_int_constant(module, "ERROR_STAGE_RELEASE_CLOSE",
                               SCION_STAGE_RELEASE_CLOSE) < 0 ||
        scion_add_int_constant(module, "ERROR_STAGE_CHDIR",
                               SCION_STAGE_CHDIR) < 0 ||
        scion_add_int_constant(module, "ERROR_STAGE_EXECVE",
                               SCION_STAGE_EXECVE) < 0 ||
        scion_add_text_constant(module, "ERROR_RECORD_FORMAT",
                                "<4sBBHI") < 0) {
        Py_DECREF(module);
        return NULL;
    }
    magic = PyBytes_FromStringAndSize("SCXE", 4);
    if (magic == NULL || PyModule_AddObject(module, "ERROR_RECORD_MAGIC", magic) < 0) {
        Py_XDECREF(magic);
        Py_DECREF(module);
        return NULL;
    }
    {
        PyObject *wait_fields = Py_BuildValue(
            "(ssssssss)", "pid", "uid", "si_code", "si_status",
            "wait_status", "return_code", "signal", "core_dumped");
        if (wait_fields == NULL ||
            PyModule_AddObject(module, "WAIT_RESULT_FIELDS", wait_fields) < 0) {
            Py_XDECREF(wait_fields);
            Py_DECREF(module);
            return NULL;
        }
    }
    return module;
}
