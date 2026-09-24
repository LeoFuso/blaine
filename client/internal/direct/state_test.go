package direct

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func TestInstallationReuseAndExclusiveLease(t *testing.T) {
	root := t.TempDir()
	a, e := OpenInstallation(root)
	if e != nil {
		t.Fatal(e)
	}
	key := append([]byte(nil), a.Key...)
	id := a.ID()
	if _, e = OpenInstallation(root); e == nil {
		t.Fatal("concurrent installation accepted")
	}
	if reused, e := a.ObserveNode("node-A"); e != nil || reused {
		t.Fatal(reused, e)
	}
	a.Close()
	b, e := OpenInstallation(root)
	if e != nil {
		t.Fatal(e)
	}
	defer b.Close()
	if id != b.ID() || !bytes.Equal(key, b.Key) {
		t.Fatal("application identity rotated")
	}
	if reused, e := b.ObserveNode("node-A"); e != nil || !reused {
		t.Fatal(reused, e)
	}
	if _, e = b.ObserveNode("node-B"); e == nil {
		t.Fatal("node changed silently")
	}
}
func TestStateRejectsSymlinksAndPublicKeys(t *testing.T) {
	root := t.TempDir()
	i, e := OpenInstallation(root)
	if e != nil {
		t.Fatal(e)
	}
	i.Close()
	key := filepath.Join(root, "direct-v1", "identity.key")
	if e = os.Chmod(key, 0644); e != nil {
		t.Fatal(e)
	}
	if _, e = OpenInstallation(root); e == nil {
		t.Fatal("public key file accepted")
	}
	if e = os.Chmod(key, 0600); e != nil {
		t.Fatal(e)
	}
	link := filepath.Join(root, "direct-v1", "tsnet", "redirect")
	if e = os.Symlink(key, link); e != nil {
		t.Fatal(e)
	}
	if _, e = OpenInstallation(root); e == nil {
		t.Fatal("redirected tsnet file accepted")
	}
}

func TestMissingApplicationKeyDoesNotSilentlyRepairExistingNode(t *testing.T) {
	root := t.TempDir()
	i, e := OpenInstallation(root)
	if e != nil {
		t.Fatal(e)
	}
	_, e = i.ObserveNode("existing-node")
	if e != nil {
		t.Fatal(e)
	}
	i.Close()
	if e = os.Remove(filepath.Join(root, "direct-v1", "identity.key")); e != nil {
		t.Fatal(e)
	}
	if _, e = OpenInstallation(root); e == nil {
		t.Fatal("lost identity silently repaired")
	}
}
