package connection

import (
	"blaine.local/client/internal/buildinfo"
	"blaine.local/client/internal/wire"
	"errors"
	"fmt"
)

type Range struct {
	Min int `json:"min"`
	Max int `json:"max"`
}
type Request struct {
	Schema         int    `json:"schema_version"`
	ClientVersion  string `json:"client_version"`
	Protocol       Range  `json:"protocol"`
	ExpectedServer string `json:"expected_server_id"`
	ClientID       string `json:"client_id"`
}
type Peer struct {
	Device    string `json:"device_id"`
	Principal string `json:"principal_id"`
	SSHUser   string `json:"ssh_user"`
	Source    string `json:"source"`
}
type Response struct {
	Schema        int               `json:"schema_version"`
	ServerID      string            `json:"server_id"`
	ServerVersion string            `json:"server_version"`
	Protocol      Range             `json:"protocol"`
	Selected      int               `json:"selected_protocol"`
	Peer          Peer              `json:"peer"`
	Registration  string            `json:"registration_status"`
	Features      []string          `json:"features"`
	Readiness     map[string]string `json:"readiness"`
}

func Hello(p Profile) Request {
	return Request{1, buildinfo.Current().ClientVersion, Range{1, 1}, p.ServerID, p.ClientID}
}
func Validate(data []byte, p Profile) (Response, error) {
	var r Response
	if e := wire.Decode(data, &r); e != nil {
		return r, errors.New("REMOTE_INVALID: malformed handshake; no ACP launch")
	}
	if r.Schema != 1 || r.Protocol.Min < 1 || r.Protocol.Max < r.Protocol.Min || r.Protocol.Min > 1 || r.Protocol.Max < 1 || r.Selected != 1 {
		return r, fmt.Errorf("INCOMPATIBLE: client %s supports protocol 1; server supports %d..%d; upgrade the incompatible installation", buildinfo.Current().ClientVersion, r.Protocol.Min, r.Protocol.Max)
	}
	if !identifier.MatchString(r.ServerID) || r.ServerVersion == "" || len(r.ServerVersion) > 128 || (p.ServerID != "" && r.ServerID != p.ServerID) {
		return r, errors.New("IDENTITY_MISMATCH: server identity changed or absent; trusted re-pairing required")
	}
	if !identifier.MatchString(r.Peer.Device) || !identifier.MatchString(r.Peer.Principal) || r.Peer.SSHUser != p.User || r.Peer.Source != "trusted-transport" {
		return r, errors.New("PEER_UNVERIFIED: host must establish trusted device, principal and intended SSH user")
	}
	for _, required := range []string{"handshake-v1", "acp-ndjson", "no-workspace-effects"} {
		found := false
		for _, f := range r.Features {
			found = found || f == required
		}
		if !found {
			return r, errors.New("INCOMPATIBLE: required host feature missing; upgrade host/client")
		}
	}
	if r.Registration != "not-implemented" {
		return r, errors.New("INCOMPATIBLE: registration semantics require E0.D")
	}
	for _, name := range []string{"runtime", "restate", "mirix", "generation", "embeddings"} {
		if r.Readiness[name] != "PASS" {
			return r, errors.New("REMOTE_UNAVAILABLE: required readiness is failed or unknown")
		}
	}
	return r, nil
}
