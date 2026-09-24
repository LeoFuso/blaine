package buildinfo

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestStableVersion(t *testing.T) {
	i := Info{1, "0.1.0", 1, "abc123", "go1.27.1", "linux", "amd64"}
	if i.String() != "blaine 0.1.0 protocol=1 commit=abc123 go=go1.27.1 platform=linux/amd64" {
		t.Fatal(i.String())
	}
	raw, err := json.Marshal(i)
	if err != nil {
		t.Fatal(err)
	}
	for _, key := range []string{"schema_version", "client_version", "protocol_version", "build_commit", "go_version", "os", "arch"} {
		if !strings.Contains(string(raw), `"`+key+`":`) {
			t.Fatal(key)
		}
	}
	if Current().ClientVersion == "" || Current().BuildCommit == "" {
		t.Fatal("missing metadata")
	}
}
