package platform

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDetectionAndPaths(t *testing.T) {
	for _, tc := range []struct {
		name, goos, release, kind, config, state string
		env                                      map[string]string
	}{
		{"linux", "linux", "6.8.0", "linux", "/home/a/.config/blaine/config.json", "/home/a/.local/state/blaine", nil},
		{"xdg", "linux", "6.8.0", "linux", "/custom config/blaine/config.json", "/state/blaine", map[string]string{"XDG_CONFIG_HOME": "/custom config", "XDG_STATE_HOME": "/state", "XDG_RUNTIME_DIR": "/run/user/1000"}},
		{"mac", "darwin", "", "darwin", "/home/a/Library/Application Support/Blaine/config.json", "/home/a/Library/Application Support/Blaine/state", map[string]string{"XDG_CONFIG_HOME": "/ignored"}},
		{"wsl-kernel", "linux", "5.15.153.1-microsoft-standard-WSL2", "wsl", "/home/a/.config/blaine/config.json", "/home/a/.local/state/blaine", nil},
		{"wsl-env-only-unverified", "linux", "6.8", "wsl", "/home/a/.config/blaine/config.json", "/home/a/.local/state/blaine", map[string]string{"WSL_DISTRO_NAME": "Ubuntu"}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			p, err := Detect(tc.goos, "amd64", "/home/a", tc.release, func(k string) string { return tc.env[k] })
			if err != nil || p.Kind != tc.kind || p.Paths.ConfigFile != tc.config || p.Paths.StateDir != tc.state {
				t.Fatalf("%+v %v", p, err)
			}
			if tc.env["XDG_RUNTIME_DIR"] != "" && p.Paths.RuntimeDir != "/run/user/1000/blaine" {
				t.Fatal(p.Paths)
			}
		})
	}
}
func TestInvalidPlatformPaths(t *testing.T) {
	for _, goos := range []string{"windows", "freebsd"} {
		if _, err := Detect(goos, "amd64", "/home/a", "", os.Getenv); err == nil {
			t.Fatal(goos)
		}
	}
	for _, key := range []string{"XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR"} {
		if _, err := Detect("linux", "amd64", "/home/a", "", func(k string) string {
			if k == key {
				return "relative"
			}
			return ""
		}); err == nil {
			t.Fatal(key)
		}
	}
	if _, err := Detect("linux", "amd64", "relative", "", os.Getenv); err == nil {
		t.Fatal("relative home")
	}
}
func TestDirectoryInspectionReadOnly(t *testing.T) {
	root := t.TempDir()
	target := filepath.Join(root, "missing", "blaine")
	if exists, err := InspectDirectory(target); exists || err != nil {
		t.Fatalf("%v %v", exists, err)
	}
	if _, err := os.Stat(filepath.Dir(target)); !os.IsNotExist(err) {
		t.Fatal("created directory")
	}
	if err := os.WriteFile(filepath.Join(root, "file"), []byte("private"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := InspectDirectory(filepath.Join(root, "file", "child")); err == nil {
		t.Fatal("accepted file ancestor")
	}
	if err := os.Symlink(root, filepath.Join(root, "link")); err != nil {
		t.Fatal(err)
	}
	if _, err := InspectDirectory(filepath.Join(root, "link", "missing")); err == nil {
		t.Fatal("accepted symlink ancestor")
	}
}
func TestExecutableDiscovery(t *testing.T) {
	p := Platform{}
	t.Setenv("PATH", t.TempDir())
	if _, err := p.LookPath("not-installed"); err == nil {
		t.Fatal("missing executable found")
	}
}
