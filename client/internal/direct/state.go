//go:build linux || darwin

package direct

import (
	"crypto/ed25519"
	"crypto/rand"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"syscall"

	"blaine.local/client/internal/platform"
	"golang.org/x/sys/unix"
)

// Installation owns one exclusive identity lease. The node store is credential
// material, not a connection cache; normal shutdown never deletes it.
type Installation struct {
	Dir  string
	Key  ed25519.PrivateKey
	lock *os.File
}

func privateDirectory(path string) error {
	if !filepath.IsAbs(path) {
		return errors.New("STATE_INVALID: absolute path required")
	}
	if _, e := platform.InspectDirectory(path); e != nil {
		return errors.New("STATE_INVALID: unsafe directory")
	}
	if e := os.MkdirAll(path, 0700); e != nil {
		return errors.New("STATE_INVALID: cannot create private directory")
	}
	st, e := os.Lstat(path)
	if e != nil || !st.IsDir() || st.Mode().Perm()&0077 != 0 {
		return errors.New("STATE_INVALID: directory must be private (0700)")
	}
	if s, ok := st.Sys().(*syscall.Stat_t); !ok || int(s.Uid) != os.Geteuid() {
		return errors.New("STATE_INVALID: directory owner")
	}
	return nil
}
func privateFile(path string, flags int) (*os.File, error) {
	fd, e := unix.Open(path, flags|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0600)
	if e != nil {
		return nil, e
	}
	f := os.NewFile(uintptr(fd), path)
	st, e := f.Stat()
	if e != nil || !st.Mode().IsRegular() || st.Mode().Perm()&0077 != 0 {
		f.Close()
		return nil, errors.New("STATE_INVALID: private regular file required")
	}
	s, ok := st.Sys().(*syscall.Stat_t)
	if !ok || int(s.Uid) != os.Geteuid() || s.Nlink != 1 {
		f.Close()
		return nil, errors.New("STATE_INVALID: file owner/link count")
	}
	return f, nil
}
func readPrivate(path string) ([]byte, error) {
	f, e := privateFile(path, unix.O_RDONLY)
	if e != nil {
		return nil, e
	}
	defer f.Close()
	b, e := io.ReadAll(io.LimitReader(f, 4097))
	if len(b) > 4096 {
		return nil, errors.New("STATE_INVALID: metadata size")
	}
	return b, e
}
func createPrivate(path string, b []byte) error {
	f, e := privateFile(path, unix.O_WRONLY|unix.O_CREAT|unix.O_EXCL)
	if e != nil {
		return e
	}
	_, e = f.Write(b)
	if e == nil {
		e = f.Sync()
	}
	return errors.Join(e, f.Close())
}
func OpenInstallation(root string) (*Installation, error) {
	dir := filepath.Join(root, "direct-v1")
	if e := privateDirectory(dir); e != nil {
		return nil, e
	}
	lock, e := privateFile(filepath.Join(dir, "installation.lock"), unix.O_RDWR|unix.O_CREAT)
	if e != nil {
		return nil, e
	}
	if e = unix.Flock(int(lock.Fd()), unix.LOCK_EX|unix.LOCK_NB); e != nil {
		lock.Close()
		return nil, errors.New("INSTANCE_BUSY: another Blaine process owns this installation")
	}
	i := &Installation{Dir: dir, lock: lock}
	seed, e := readPrivate(filepath.Join(dir, "identity.key"))
	if errors.Is(e, os.ErrNotExist) {
		entries, _ := os.ReadDir(filepath.Join(dir, "tsnet"))
		_, nodeErr := os.Lstat(filepath.Join(dir, "node-id"))
		_, profileErr := os.Lstat(filepath.Join(dir, "connection.json"))
		if len(entries) > 0 || !errors.Is(nodeErr, os.ErrNotExist) || !errors.Is(profileErr, os.ErrNotExist) {
			i.Close()
			return nil, errors.New("IDENTITY_CHANGED: application key missing from existing installation")
		}
		seed = make([]byte, ed25519.SeedSize)
		_, e = rand.Read(seed)
		if e == nil {
			e = createPrivate(filepath.Join(dir, "identity.key"), seed)
		}
	}
	if e != nil || len(seed) != ed25519.SeedSize {
		i.Close()
		return nil, errors.New("STATE_INVALID: installation key")
	}
	i.Key = ed25519.NewKeyFromSeed(seed)
	if e = privateDirectory(filepath.Join(dir, "tsnet")); e != nil {
		i.Close()
		return nil, e
	}
	// Refuse redirected or permissive existing store files, including tsnet's keys.
	e = filepath.WalkDir(filepath.Join(dir, "tsnet"), func(p string, d os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if d.IsDir() {
			return privateDirectory(p)
		}
		f, err := privateFile(p, unix.O_RDONLY)
		if err == nil {
			f.Close()
		}
		return err
	})
	if e != nil {
		i.Close()
		return nil, errors.New("STATE_INVALID: unsafe embedded node store")
	}
	return i, nil
}
func (i *Installation) ID() string { return keyID("ws-", i.Key.Public().(ed25519.PublicKey)) }
func (i *Installation) Close() {
	if i.lock != nil {
		unix.Flock(int(i.lock.Fd()), unix.LOCK_UN)
		i.lock.Close()
		i.lock = nil
	}
}
func (i *Installation) ObserveNode(node string) (bool, error) {
	if node == "" || strings.ContainsAny(node, "\r\n\x00") {
		return false, errors.New("IDENTITY_INVALID: node")
	}
	path := filepath.Join(i.Dir, "node-id")
	b, e := readPrivate(path)
	if errors.Is(e, os.ErrNotExist) {
		return false, createPrivate(path, []byte(node))
	}
	if e != nil || string(b) != node {
		return false, errors.New("IDENTITY_CHANGED: explicit review/reset required; state preserved")
	}
	return true, nil
}
