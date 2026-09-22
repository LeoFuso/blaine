//go:build linux || darwin

// Package process relays a trusted transport's stdio without parsing or logging.
// Only file descriptors are accepted: exec inherits them directly, so no blocked
// stdin-copy goroutine can keep Wait alive after cancellation or early exit.
package process

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
)

type Spec struct {
	Executable string
	Args       []string
}
type Streams struct{ In, Out, Err *os.File }

// Run starts no shell and owns a new POSIX process group on Linux, macOS and WSL.
// Cancellation hard-stops the entire group; transport cleanup is not Task cancel.
// Descendants must stay in this group (no daemonizing/setsid transport helpers).
func Run(ctx context.Context, spec Spec, streams Streams) (int, error) {
	if !filepath.IsAbs(spec.Executable) || streams.In == nil || streams.Out == nil || streams.Err == nil {
		return 1, errors.New("absolute executable and all three stdio files are required")
	}
	if ctx.Err() != nil {
		return 130, ctx.Err()
	}
	cmd := exec.CommandContext(ctx, spec.Executable, spec.Args...)
	cmd.Stdin, cmd.Stdout, cmd.Stderr = streams.In, streams.Out, streams.Err
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	kill := func() error {
		err := syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
		if errors.Is(err, syscall.ESRCH) {
			return os.ErrProcessDone
		}
		return err
	}
	cmd.Cancel = kill
	if err := cmd.Start(); err != nil {
		return 1, errors.New("transport process could not start")
	}
	err := cmd.Wait()
	// Even a normally exiting transport must not leave same-group helpers running.
	cleanupErr := kill()
	if cleanupErr != nil && !errors.Is(cleanupErr, os.ErrProcessDone) {
		return 1, errors.New("transport process group cleanup failed")
	}
	if ctx.Err() != nil {
		return 130, ctx.Err()
	}
	if err == nil {
		return 0, nil
	}
	var exited *exec.ExitError
	if errors.As(err, &exited) {
		if status, ok := exited.Sys().(syscall.WaitStatus); ok && status.Signaled() {
			return 128 + int(status.Signal()), nil
		}
		return exited.ExitCode(), nil
	}
	return 1, errors.New("transport process wait failed")
}
