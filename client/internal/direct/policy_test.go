package direct

import (
	"net/netip"
	"testing"

	"tailscale.com/client/tailscale/apitype"
	"tailscale.com/tailcfg"
)

func TestAdmittedIdentityIgnoresAddressAndDescriptiveName(t *testing.T) {
	who := &apitype.WhoIsResponse{Node: &tailcfg.Node{StableID: "node-A", Name: "original.fixture", Addresses: []netip.Prefix{netip.MustParsePrefix("100.64.0.1/32")}}, UserProfile: &tailcfg.UserProfile{ID: 42}}
	a, err := AdmittedPeer(who)
	if err != nil {
		t.Fatal(err)
	}
	who.Node.Name = "renamed.fixture"
	who.Node.Addresses = []netip.Prefix{netip.MustParsePrefix("100.64.1.2/32")}
	b, err := AdmittedPeer(who)
	if err != nil || a.NodeID != b.NodeID {
		t.Fatal("metadata/address changed identity", b, err)
	}
	who.Node.StableID = "node-B"
	c, err := AdmittedPeer(who)
	if err != nil || c.NodeID == a.NodeID {
		t.Fatal("same metadata inherited identity", c, err)
	}
	for _, invalid := range []*apitype.WhoIsResponse{nil, {}, {Node: &tailcfg.Node{StableID: "node", Expired: true}}, {Node: &tailcfg.Node{StableID: "node"}}} {
		if _, err = AdmittedPeer(invalid); err == nil {
			t.Fatal("unverified identity accepted")
		}
	}
}

func TestTransportPolicyBindsObservedNodeAndPrincipal(t *testing.T) {
	who := &apitype.WhoIsResponse{Node: &tailcfg.Node{StableID: "designated-node"}, UserProfile: &tailcfg.UserProfile{ID: 42}}
	if _, e := Authorize(who, "42", []string{"designated-node"}); e != nil {
		t.Fatal(e)
	}
	for _, test := range []struct {
		principal string
		nodes     []string
	}{{"wrong", []string{"designated-node"}}, {"42", []string{"other-node"}}, {"", nil}} {
		if _, e := Authorize(who, test.principal, test.nodes); e == nil {
			t.Fatal("unexpected principal/node admitted")
		}
	}
	who.Node.Expired = true
	if _, e := Authorize(who, "42", []string{"designated-node"}); e == nil {
		t.Fatal("expired admitted")
	}
	who.Node.Expired = false
	who.Node.Tags = []string{"tag:blaine-client"}
	if _, e := Authorize(who, "42", []string{"designated-node"}); e == nil {
		t.Fatal("tagged node treated as its former owner")
	}
	if _, e := Authorize(who, "tag:blaine-client", []string{"designated-node"}); e != nil {
		t.Fatal(e)
	}
}
func TestVerifiedProfileRejectsIdentityChange(t *testing.T) {
	i, e := OpenInstallation(t.TempDir())
	if e != nil {
		t.Fatal(e)
	}
	defer i.Close()
	b, _, _ := keys(t)
	n := &Network{Installation: i, Bootstrap: b, Node: "node-A"}
	if e = n.saveProfile(); e != nil {
		t.Fatal(e)
	}
	if e = n.checkProfile(); e != nil {
		t.Fatal(e)
	}
	n.Node = "node-B"
	if e = n.checkProfile(); e == nil {
		t.Fatal("profile node changed silently")
	}
	n.Node = "node-A"
	n.Bootstrap.ServerID = "other"
	if e = n.checkProfile(); e == nil {
		t.Fatal("profile deployment changed silently")
	}
}
