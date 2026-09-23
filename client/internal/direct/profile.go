package direct

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"time"

	"blaine.local/client/internal/wire"
)

type Profile struct {
	Schema        int    `json:"schema"`
	Endpoint      string `json:"endpoint"`
	ServerID      string `json:"server_id"`
	ServerKey     string `json:"server_public_key"`
	HubNode       string `json:"hub_node_id"`
	WorkstationID string `json:"workstation_id"`
	Node          string `json:"node_id"`
	Protocol      int    `json:"protocol"`
	VerifiedAt    string `json:"last_verified_at"`
}

func (n *Network) expectedProfile() Profile {
	return Profile{1, n.Bootstrap.Endpoint, n.Bootstrap.ServerID, n.Bootstrap.ServerKey, n.Bootstrap.HubNode, n.Installation.ID(), n.Node, Protocol, ""}
}
func (n *Network) checkProfile() error {
	b, e := readPrivate(filepath.Join(n.Installation.Dir, "connection.json"))
	if errors.Is(e, os.ErrNotExist) {
		return nil
	}
	if e != nil {
		return errors.New("STATE_INVALID: connection profile")
	}
	var p Profile
	if wire.Decode(b, &p) != nil {
		return errors.New("STATE_INVALID: connection profile")
	}
	p.VerifiedAt = ""
	if p != n.expectedProfile() {
		return errors.New("IDENTITY_CHANGED: deployment/installation profile differs; explicit review required")
	}
	return nil
}
func (n *Network) saveProfile() error {
	if e := n.checkProfile(); e != nil {
		return e
	}
	p := n.expectedProfile()
	p.VerifiedAt = time.Now().UTC().Format(time.RFC3339)
	b, _ := json.Marshal(p)
	temp, e := os.CreateTemp(n.Installation.Dir, ".connection-*")
	if e != nil {
		return e
	}
	defer os.Remove(temp.Name())
	_, e = temp.Write(b)
	if e == nil {
		e = temp.Sync()
	}
	e = errors.Join(e, temp.Close())
	if e != nil {
		return e
	}
	return os.Rename(temp.Name(), filepath.Join(n.Installation.Dir, "connection.json"))
}
