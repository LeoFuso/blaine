//go:build linux || darwin

package process

import (
	"errors"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"unsafe"
)

var terminalMu sync.Mutex

func terminalGroup(f *os.File) (int32, error) {
	var group int32
	_, _, err := syscall.Syscall(syscall.SYS_IOCTL, f.Fd(), syscall.TIOCGPGRP, uintptr(unsafe.Pointer(&group)))
	if err != 0 {
		return 0, err
	}
	return group, nil
}

// IsTerminal uses the actual terminal interface, not character-device mode bits
// (which would incorrectly classify redirected /dev/null as interactive).
func IsTerminal(f *os.File) bool {
	if f == nil {
		return false
	}
	_, err := terminalGroup(f)
	return err == nil
}

// borrowTerminal refuses background/non-terminal callers. The child receives
// foreground ownership via SysProcAttr; restoration permits normal job control.
// Sudo reads its own controlling terminal, never a Blaine password prompt.
func borrowTerminal(f *os.File) (func() error, error) {
	terminalMu.Lock()
	group, err := terminalGroup(f)
	if err != nil || group != int32(syscall.Getpgrp()) {
		terminalMu.Unlock()
		return nil, errors.New("host setup requires a foreground terminal")
	}
	return func() error {
		signal.Ignore(syscall.SIGTTOU)
		_, _, restoreErr := syscall.Syscall(syscall.SYS_IOCTL, f.Fd(), syscall.TIOCSPGRP, uintptr(unsafe.Pointer(&group)))
		signal.Reset(syscall.SIGTTOU)
		terminalMu.Unlock()
		if restoreErr != 0 {
			return errors.New("could not restore terminal foreground ownership")
		}
		return nil
	}, nil
}
