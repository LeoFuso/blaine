package direct

import (
	"errors"
	"strconv"

	"tailscale.com/client/tailscale/apitype"
)

// Authorize consumes the host LocalAPI observation for the accepted socket. It
// is an E0 transport allowlist, not workstation registration or Task authority.
func Authorize(who *apitype.WhoIsResponse, expected string, allowed []string) (Peer, error) {
	if who == nil || who.Node == nil || who.Node.Expired {
		return Peer{}, errors.New("TRANSPORT_DENIED: peer unavailable or expired")
	}
	node := string(who.Node.StableID)
	permitted := false
	for _, id := range allowed {
		if node != "" && id == node {
			permitted = true
		}
	}
	principal := ""
	if len(who.Node.Tags) > 0 {
		for _, tag := range who.Node.Tags {
			if tag == expected {
				principal = tag
			}
		}
	} else if who.UserProfile != nil {
		principal = strconv.FormatInt(int64(who.UserProfile.ID), 10)
	}
	if !permitted || expected == "" || principal != expected {
		return Peer{}, errors.New("TRANSPORT_DENIED: deployment policy")
	}
	return Peer{NodeID: node, PrincipalID: principal}, nil
}
