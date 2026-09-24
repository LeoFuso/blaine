// Package buildinfo contains offline build metadata; Protocol is reserved for the
// future Blaine handshake, independent of ACP negotiation.
package buildinfo

import (
	"fmt"
	"runtime"
)

var Version = "0.1.0-dev"
var Commit = "unknown"

const Protocol = 2

type Info struct {
	SchemaVersion   int    `json:"schema_version"`
	ClientVersion   string `json:"client_version"`
	ProtocolVersion int    `json:"protocol_version"`
	BuildCommit     string `json:"build_commit"`
	GoVersion       string `json:"go_version"`
	OS              string `json:"os"`
	Arch            string `json:"arch"`
}

func Current() Info {
	return Info{1, Version, Protocol, Commit, runtime.Version(), runtime.GOOS, runtime.GOARCH}
}
func (i Info) String() string {
	return fmt.Sprintf("blaine %s protocol=%d commit=%s go=%s platform=%s/%s", i.ClientVersion, i.ProtocolVersion, i.BuildCommit, i.GoVersion, i.OS, i.Arch)
}
