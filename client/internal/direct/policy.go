package direct

import (
	"errors"
	"strconv"

	"tailscale.com/client/tailscale/apitype"
)

// Authorize consumes the host LocalAPI observation for the accepted socket. It
// is an E0 transport allowlist, not workstation registration or Task authority.
func Authorize(who *apitype.WhoIsResponse, expected string, allowed []string) (Peer, error) {
	peer, err := AdmittedPeer(who)
	if err != nil {
		return Peer{}, err
	}
	for _, tag := range who.Node.Tags {
		if tag == expected {
			peer.PrincipalID = tag
		}
	}
	permitted := false
	for _, node := range allowed {
		if node == peer.NodeID {
			permitted = true
		}
	}
	if !permitted || expected == "" || peer.PrincipalID != expected {
		return Peer{}, errors.New("TRANSPORT_DENIED: deployment policy")
	}
	return peer, nil
}

// AdmittedPeer is called only for a socket accepted on the verified private Hub
// listener. Tailscale enforces service admission; this validates its observation,
// without an application per-device approval list. Forwarding headers are ignored.
func AdmittedPeer(who *apitype.WhoIsResponse) (Peer, error) {
	if who == nil || who.Node == nil || who.Node.Expired {
		return Peer{}, errors.New("TRANSPORT_DENIED: peer unavailable or expired")
	}
	node := string(who.Node.StableID)
	principal := ""
	if len(who.Node.Tags) > 0 {
		principal = who.Node.Tags[0]
	} else if who.UserProfile != nil {
		principal = strconv.FormatInt(int64(who.UserProfile.ID), 10)
	}
	if node == "" || principal == "" || principal == "0" {
		return Peer{}, errors.New("TRANSPORT_DENIED: deployment policy")
	}
	peer := Peer{NodeID: node, PrincipalID: principal}
	if who.Node.Hostinfo.Valid() {
		peer.Metadata = PeerMetadata{who.Node.Hostinfo.Hostname(), who.Node.Hostinfo.OS(), who.Node.Hostinfo.GoArch()}
	}
	return peer, nil
}
