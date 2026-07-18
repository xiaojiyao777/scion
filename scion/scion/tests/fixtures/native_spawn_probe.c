#define _GNU_SOURCE

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/types.h>
#include <unistd.h>

static int
parse_nonnegative(const char *text, unsigned long *value)
{
    char *end = NULL;
    unsigned long parsed;

    if (text == NULL || *text == '\0' || *text == '-') {
        return -1;
    }
    errno = 0;
    parsed = strtoul(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0') {
        return -1;
    }
    *value = parsed;
    return 0;
}

static int
write_all(int fd, const void *buffer, size_t length)
{
    const unsigned char *cursor = buffer;

    while (length > 0) {
        ssize_t written = write(fd, cursor, length);
        if (written > 0) {
            cursor += (size_t)written;
            length -= (size_t)written;
            continue;
        }
        if (written < 0 && errno == EINTR) {
            continue;
        }
        return -1;
    }
    return 0;
}

static int
write_sentinel(const char *path, const char *body)
{
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    size_t length = strlen(body);
    int saved_errno;

    if (fd < 0) {
        return -1;
    }
    if (write_all(fd, body, length) < 0) {
        saved_errno = errno;
        (void)close(fd);
        errno = saved_errno;
        return -1;
    }
    if (close(fd) < 0) {
        return -1;
    }
    return 0;
}

static int
fd_is_blocking(int fd)
{
    int flags = fcntl(fd, F_GETFL);
    return flags >= 0 && (flags & O_NONBLOCK) == 0;
}

static int
inspect_fd_table(void)
{
    DIR *directory = opendir("/proc/self/fd");
    struct dirent *entry;
    int scan_fd;
    int result = 0;

    if (directory == NULL) {
        return -1;
    }
    scan_fd = dirfd(directory);
    errno = 0;
    while ((entry = readdir(directory)) != NULL) {
        char *end = NULL;
        long fd;

        errno = 0;
        fd = strtol(entry->d_name, &end, 10);
        if (errno != 0 || end == entry->d_name || *end != '\0') {
            errno = 0;
            continue;
        }
        if (fd > 2 && fd != scan_fd) {
            result = -1;
            errno = EPROTO;
            break;
        }
    }
    if (errno != 0 && result == 0) {
        result = -1;
    }
    if (closedir(directory) < 0 && result == 0) {
        result = -1;
    }
    return result;
}

static int
inspect_signals(void)
{
    sigset_t mask;
    sigset_t pending;
    int signal_number;

    if (sigprocmask(SIG_SETMASK, NULL, &mask) < 0 ||
        sigpending(&pending) < 0) {
        return -1;
    }
    for (signal_number = 1; signal_number < NSIG; signal_number++) {
        struct sigaction action;
        int masked = sigismember(&mask, signal_number);
        int queued = sigismember(&pending, signal_number);

        if (masked < 0 || queued < 0 || masked != 0 || queued != 0) {
            errno = EPROTO;
            return -1;
        }
        if (signal_number == SIGKILL || signal_number == SIGSTOP) {
            continue;
        }
        errno = 0;
        if (sigaction(signal_number, NULL, &action) < 0) {
            if (errno == EINVAL) {
                continue;
            }
            return -1;
        }
        if (action.sa_handler != SIG_DFL) {
            errno = EPROTO;
            return -1;
        }
        if ((action.sa_flags &
             (SA_NOCLDSTOP | SA_NOCLDWAIT | SA_NODEFER | SA_ONSTACK |
              SA_RESETHAND | SA_RESTART | SA_SIGINFO)) != 0) {
            errno = EPROTO;
            return -1;
        }
    }
    return 0;
}

static int
role_inspect(void)
{
    struct stat status;

    if (fstat(STDIN_FILENO, &status) < 0 || !S_ISCHR(status.st_mode) ||
        major(status.st_rdev) != 1U || minor(status.st_rdev) != 3U ||
        !fd_is_blocking(STDIN_FILENO) || !fd_is_blocking(STDOUT_FILENO) ||
        !fd_is_blocking(STDERR_FILENO) || inspect_signals() < 0 ||
        inspect_fd_table() < 0) {
        return 70;
    }
    if (write_all(STDOUT_FILENO, "INSPECT_OK\n", 11U) < 0 ||
        write_all(STDERR_FILENO, "INSPECT_ERR\n", 12U) < 0) {
        return 71;
    }
    return 0;
}

static int
role_emit(const char *count_text)
{
    unsigned long count;
    unsigned long offset = 0;
    unsigned char stdout_block[4096];
    unsigned char stderr_block[4096];
    size_t index;

    if (parse_nonnegative(count_text, &count) < 0) {
        return 64;
    }
    for (index = 0; index < sizeof(stdout_block); index++) {
        stdout_block[index] = (unsigned char)(index % 251U);
        stderr_block[index] = (unsigned char)(255U - (index % 251U));
    }
    while (offset < count) {
        unsigned long remaining = count - offset;
        size_t chunk = remaining < sizeof(stdout_block)
            ? (size_t)remaining : sizeof(stdout_block);
        if (write_all(STDOUT_FILENO, stdout_block, chunk) < 0 ||
            write_all(STDERR_FILENO, stderr_block, chunk) < 0) {
            return 72;
        }
        offset += (unsigned long)chunk;
    }
    return 0;
}

static int
role_descendant(const char *sentinel)
{
    pid_t child = fork();

    if (child < 0) {
        return 73;
    }
    if (child == 0) {
        char body[64];
        int length;

        if (setsid() < 0) {
            _exit(74);
        }
        (void)close(STDIN_FILENO);
        (void)close(STDOUT_FILENO);
        (void)close(STDERR_FILENO);
        length = snprintf(body, sizeof(body), "%ld\n", (long)getpid());
        if (length < 0 || (size_t)length >= sizeof(body) ||
            write_sentinel(sentinel, body) < 0) {
            _exit(75);
        }
        for (;;) {
            pause();
        }
    }
    return 0;
}

int
main(int argc, char **argv)
{
    unsigned long number;

    if (argc < 2) {
        return 64;
    }
    if (strcmp(argv[1], "inspect") == 0 && argc == 2) {
        return role_inspect();
    }
    if (strcmp(argv[1], "fds") == 0 && argc == 2) {
        return inspect_fd_table() == 0 ? 0 : 79;
    }
    if (strcmp(argv[1], "emit") == 0 && argc == 3) {
        return role_emit(argv[2]);
    }
    if (strcmp(argv[1], "exit") == 0 && argc == 3 &&
        parse_nonnegative(argv[2], &number) == 0 && number <= 255UL) {
        return (int)number;
    }
    if (strcmp(argv[1], "raise") == 0 && argc == 3 &&
        parse_nonnegative(argv[2], &number) == 0 &&
        number > 0UL && number < (unsigned long)NSIG) {
        if (raise((int)number) < 0) {
            return 76;
        }
        return 77;
    }
    if (strcmp(argv[1], "sentinel") == 0 && argc == 3) {
        return write_sentinel(argv[2], "executed\n") == 0 ? 0 : 78;
    }
    if (strcmp(argv[1], "descendant") == 0 && argc == 3) {
        return role_descendant(argv[2]);
    }
    if (strcmp(argv[1], "pause") == 0 && argc == 2) {
        for (;;) {
            pause();
        }
    }
    if (strcmp(argv[1], "abort") == 0 && argc == 2) {
        abort();
    }
    return 64;
}
