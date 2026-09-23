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
	// Protocol upgrade changes no deployment or installation binding. All pins
	// still compare exactly; the server-assigned registry receipt is separate.
	if p.Protocol == 1 {
		p.Protocol = Protocol
	}
	if p != n.expectedProfile() {
		return errors.New("IDENTITY_CHANGED: deployment/installation profile differs; explicit review required")
	}
	return nil
}

type registrationReceipt struct {
	WorkstationID string `json:"workstation_id"`
	Node          string `json:"transport_node_id"`
	ServerID      string `json:"server_id"`
}

// RegisteredWorkstation reads the cached signed-handshake result. It is not a
// probe of remote presence or admission, and never starts tsnet or writes state.
func RegisteredWorkstation(root string) (string, error) {
	b, e := readPrivate(filepath.Join(root, "direct-v1", "registration.json"))
	if e != nil {
		return "", e
	}
	var r registrationReceipt
	if wire.Decode(b, &r) != nil || !validWorkstationID(r.WorkstationID) || r.Node == "" || r.ServerID != Deployment().ServerID {
		return "", errors.New("STATE_INVALID: registration receipt")
	}
	return r.WorkstationID, nil
}

func (n *Network) saveRegistration(id string) error {
	if !validWorkstationID(id) {
		return errors.New("REGISTRATION_INVALID")
	}
	path := filepath.Join(n.Installation.Dir, "registration.json")
	expected := registrationReceipt{id, n.Node, n.Bootstrap.ServerID}
	old, e := readPrivate(path)
	if e == nil {
		var r registrationReceipt
		if wire.Decode(old, &r) != nil || r != expected {
			return errors.New("REGISTRATION_CHANGED: recorded binding differs")
		}
		return nil
	}
	if !errors.Is(e, os.ErrNotExist) {
		return e
	}
	b, _ := json.Marshal(expected)
	temp, e := os.CreateTemp(n.Installation.Dir, ".registration-*")
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
	return os.Rename(temp.Name(), path)
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
