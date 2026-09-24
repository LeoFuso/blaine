package connection

import (
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"

	"blaine.local/client/internal/platform"
	"blaine.local/client/internal/wire"
)

const Mode = "tailscale-ssh"

type Profile struct {
	Schema    int    `json:"schema_version"`
	Host      string `json:"host"`
	User      string `json:"ssh_user"`
	Transport string `json:"transport"`
	ClientID  string `json:"client_id"`
	ServerID  string `json:"server_id"`
}

var hostName = regexp.MustCompile(`^[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?$`)
var userName = regexp.MustCompile(`^[a-z_][a-z0-9_-]{0,63}$`)
var identifier = regexp.MustCompile(`^[a-zA-Z0-9_-]{1,128}$`)

func (p Profile) Validate(paired bool) error {
	if p.Schema != 1 || !hostName.MatchString(p.Host) || !userName.MatchString(p.User) || p.Transport != Mode || !identifier.MatchString(p.ClientID) || (paired && !identifier.MatchString(p.ServerID)) {
		return errors.New("LOCAL_INVALID: invalid host profile; use a private MagicDNS host and explicit SSH user")
	}
	return nil
}
func New(host, user string) (Profile, error) {
	b := make([]byte, 16)
	if _, e := rand.Read(b); e != nil {
		return Profile{}, e
	}
	b[6] = (b[6] & 15) | 64
	b[8] = (b[8] & 63) | 128
	p := Profile{1, host, user, Mode, fmt.Sprintf("%x-%x-%x-%x-%x", b[:4], b[4:6], b[6:8], b[8:10], b[10:]), ""}
	return p, p.Validate(false)
}
func Load(path string) (Profile, error) {
	var p Profile
	if _, e := platform.InspectDirectory(filepath.Dir(path)); e != nil {
		return p, e
	}
	info, e := os.Lstat(path)
	if e != nil {
		return p, e
	}
	if !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 {
		return p, errors.New("LOCAL_INVALID: profile must be a private regular file")
	}
	f, e := os.Open(path)
	if e != nil {
		return p, e
	}
	defer f.Close()
	opened, e := f.Stat()
	if e != nil || !os.SameFile(info, opened) {
		return p, errors.New("LOCAL_INVALID: profile changed")
	}
	data, e := io.ReadAll(io.LimitReader(f, wire.Limit+1))
	if e != nil {
		return p, e
	}
	if e = wire.Decode(data, &p); e != nil {
		return p, errors.New("LOCAL_INVALID: malformed profile")
	}
	return p, p.Validate(true)
}

// SaveNew publishes a complete first pairing without overwriting concurrent or
// existing state. Re-pairing/migration is deliberately not automatic in E0.C.
func SaveNew(path string, p Profile) error {
	if e := p.Validate(true); e != nil {
		return e
	}
	dir := filepath.Dir(path)
	if _, e := platform.InspectDirectory(dir); e != nil {
		return e
	}
	if e := os.MkdirAll(dir, 0700); e != nil {
		return e
	}
	info, e := os.Stat(dir)
	if e != nil || info.Mode().Perm()&0077 != 0 {
		return errors.New("LOCAL_INVALID: profile directory must be private")
	}
	f, e := os.CreateTemp(dir, ".connection-")
	if e != nil {
		return e
	}
	defer os.Remove(f.Name())
	defer f.Close()
	if e = json.NewEncoder(f).Encode(p); e != nil {
		return e
	}
	if e = f.Sync(); e != nil {
		return e
	}
	if e = f.Close(); e != nil {
		return e
	}
	// Same-directory hard link is atomic and fails if any destination exists.
	if e = os.Link(f.Name(), path); e != nil {
		return errors.New("LOCAL_INVALID: profile exists or concurrent creation; inspect before retrying")
	}
	return nil
}
