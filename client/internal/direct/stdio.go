//go:build linux || darwin

package direct

import (
	"context"
	"errors"
	"io"
	"os"
	"runtime"
	"time"

	"blaine.local/client/internal/process"
	"golang.org/x/sys/unix"
)

// Inherited os.Stdin/os.Stdout may be blocking descriptors outside Go's poller.
// Closing them from another goroutine can wait for the blocked Read/Write itself.
// Use owned duplicates, nonblocking syscalls and bounded POSIX poll instead. This
// also avoids Darwin kqueue's documented FIFO last-writer/EOF limitation. Bytes
// are unchanged; the E0.A subprocess descriptor forwarding path is untouched.
// The caller must exclusively own stdio while borrowed; dup shares status flags.
type interruptibleFile struct {
	ctx      context.Context
	fd       int
	flags    int
	original *os.File
}

func borrowFile(ctx context.Context, original *os.File) (*interruptibleFile, error) {
	if original == nil {
		return nil, errors.New("LOCAL_INVALID: missing ACP descriptor")
	}
	// SyscallConn avoids File.Fd changing the original's nonblocking status.
	raw, e := original.SyscallConn()
	if e != nil {
		return nil, e
	}
	var fd, flags int
	var operationErr error
	e = raw.Control(func(value uintptr) {
		flags, operationErr = unix.FcntlInt(value, unix.F_GETFL, 0)
		if operationErr != nil {
			return
		}
		fd, operationErr = unix.FcntlInt(value, unix.F_DUPFD_CLOEXEC, 0)
	})
	if e != nil {
		return nil, e
	}
	if operationErr != nil {
		return nil, operationErr
	}
	if e = unix.SetNonblock(fd, true); e != nil {
		unix.Close(fd)
		return nil, e
	}
	return &interruptibleFile{ctx: ctx, fd: fd, flags: flags, original: original}, nil
}

// Close follows completion of all users. Cancellation interrupts poll within
// 100 ms; it never races Close against a blocking kernel read/write.
func (f *interruptibleFile) Close() error {
	if f.fd < 0 {
		return nil
	}
	_, e := unix.FcntlInt(uintptr(f.fd), unix.F_SETFL, f.flags)
	e = errors.Join(e, unix.Close(f.fd))
	f.fd = -1
	runtime.KeepAlive(f.original)
	return e
}
func (f *interruptibleFile) wait(event int16) error {
	for {
		if e := f.ctx.Err(); e != nil {
			return e
		}
		timeout := 100
		if deadline, ok := f.ctx.Deadline(); ok {
			left := time.Until(deadline)
			if left <= 0 {
				return context.DeadlineExceeded
			}
			if ms := int((left + time.Millisecond - 1) / time.Millisecond); ms < timeout {
				timeout = ms
			}
		}
		descriptors := []unix.PollFd{{Fd: int32(f.fd), Events: event}}
		n, e := unix.Poll(descriptors, timeout)
		if errors.Is(e, unix.EINTR) {
			continue
		}
		if e != nil {
			return e
		}
		if descriptors[0].Revents&unix.POLLNVAL != 0 {
			return os.ErrClosed
		}
		// HUP/ERR also wake the operation so read drains buffered bytes / sees EOF
		// and write reports EPIPE. Only EAGAIN causes another bounded wait.
		if n > 0 {
			return nil
		}
	}
}
func (f *interruptibleFile) Read(b []byte) (int, error) {
	if len(b) == 0 {
		return 0, nil
	}
	for {
		if e := f.ctx.Err(); e != nil {
			return 0, e
		}
		n, e := unix.Read(f.fd, b)
		if errors.Is(e, unix.EINTR) {
			continue
		}
		if errors.Is(e, unix.EAGAIN) {
			if e = f.wait(unix.POLLIN); e != nil {
				return 0, e
			}
			continue
		}
		if n < 0 {
			n = 0
		}
		if n == 0 && e == nil {
			return 0, io.EOF
		}
		return n, e
	}
}
func (f *interruptibleFile) Write(b []byte) (int, error) {
	written := 0
	for written < len(b) {
		if e := f.ctx.Err(); e != nil {
			return written, e
		}
		n, e := unix.Write(f.fd, b[written:])
		if n > 0 {
			written += n
		}
		if errors.Is(e, unix.EINTR) {
			continue
		}
		if errors.Is(e, unix.EAGAIN) {
			if e = f.wait(unix.POLLOUT); e != nil {
				return written, e
			}
			continue
		}
		if e != nil {
			return written, e
		}
		if n == 0 {
			return written, io.ErrShortWrite
		}
	}
	return written, nil
}

type interruptibleStdio struct{ In, Out *interruptibleFile }

func borrowStdio(ctx context.Context, s process.Streams) (*interruptibleStdio, error) {
	in, e := borrowFile(ctx, s.In)
	if e != nil {
		return nil, e
	}
	out, e := borrowFile(ctx, s.Out)
	if e != nil {
		in.Close()
		return nil, e
	}
	return &interruptibleStdio{in, out}, nil
}
func (s *interruptibleStdio) Close() error { return errors.Join(s.Out.Close(), s.In.Close()) }
