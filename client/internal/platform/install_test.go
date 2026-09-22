package platform

import (
	"context"
	"errors"
	"os"
	"strings"
	"testing"

	"blaine.local/client/internal/process"
)

func aptFixture(t *testing.T) *Tailscale {
	a := fakeTailscale(t, "linux")
	a.ReadFile = func(string) ([]byte, error) { return []byte("ID=ubuntu\nVERSION_CODENAME=resolute\n"), nil }
	a.Lookup = func(name string) (string, error) { return "/usr/bin/" + name, nil }
	return a
}
func TestInstallationPolicy(t *testing.T) {
	a := aptFixture(t)
	if p := a.Installation(); p.Kind != "apt" || p.Repository != "https://pkgs.tailscale.com/stable/ubuntu/resolute" {
		t.Fatal(p)
	}
	for _, distro := range []string{"ID=debian\nVERSION_CODENAME=trixie", "ID=ubuntu\nVERSION_CODENAME=noble"} {
		a.ReadFile = func(string) ([]byte, error) { return []byte(distro), nil }
		if a.Installation().Kind != "apt" {
			t.Fatal(distro)
		}
	}
	for _, distro := range []string{"ID=fedora\nVERSION_CODENAME=40", "ID=ubuntu\nVERSION_CODENAME=$(id)", "ID=ubuntu\nVERSION_CODENAME=unknown"} {
		a.ReadFile = func(string) ([]byte, error) { return []byte(distro), nil }
		if a.Installation().Kind != "manual" {
			t.Fatal(distro)
		}
	}
	a = aptFixture(t)
	a.Stat = func(string) (os.FileInfo, error) { return nil, os.ErrPermission }
	if a.Installation().Kind != "manual" {
		t.Fatal("existing/inaccessible config accepted")
	}
	for _, kind := range []string{"wsl", "darwin"} {
		a = fakeTailscale(t, kind)
		if a.Installation().Kind == "apt" {
			t.Fatal("nested or competing install")
		}
	}
}
func TestInstallStructuredCommandsAndFailure(t *testing.T) {
	for _, failAt := range []int{0, 1, 2, 3, 4} {
		t.Run(string(rune('0'+failAt)), func(t *testing.T) {
			a := aptFixture(t)
			var calls []process.Spec
			var tempFiles []string
			a.Run = func(ctx context.Context, s process.Spec, _ *os.File, _ func([]byte)) ([]byte, int, error) {
				if _, ok := ctx.Deadline(); !ok {
					t.Fatal("unbounded")
				}
				calls = append(calls, s)
				if s.Executable != "/usr/bin/sudo" || !s.Foreground || strings.Join(s.Args[:2], " ") != "-k --" {
					t.Fatal(s)
				}
				if len(calls) <= 2 {
					source := s.Args[len(s.Args)-2]
					tempFiles = append(tempFiles, source)
					data, err := os.ReadFile(source)
					if err != nil {
						t.Fatal(err)
					}
					if len(calls) == 2 && string(data) != "deb [signed-by=/usr/share/keyrings/tailscale-archive-keyring.gpg] https://pkgs.tailscale.com/stable/ubuntu resolute main\n" {
						t.Fatal(string(data))
					}
				}
				if len(calls) == failAt {
					return []byte("secret-token"), 1, errors.New("secret-token")
				}
				return nil, 0, nil
			}
			err := a.install(context.Background(), nil, func(_ context.Context, url string) ([]byte, error) {
				if url != "https://pkgs.tailscale.com/stable/ubuntu/resolute.noarmor.gpg" {
					t.Fatal(url)
				}
				return []byte("public-key-fixture"), nil
			})
			if failAt == 0 {
				if err != nil || len(calls) != 4 {
					t.Fatal(err, calls)
				}
			} else {
				if err == nil || len(calls) != failAt || strings.Contains(err.Error(), "secret") {
					t.Fatal(err, calls)
				}
			}
			for _, p := range tempFiles {
				if _, err := os.Stat(p); !os.IsNotExist(err) {
					t.Fatal("temporary installation metadata persisted")
				}
			}
		})
	}
}
func TestDownloadFailureNeverMutates(t *testing.T) {
	a := aptFixture(t)
	if err := a.install(context.Background(), nil, func(context.Context, string) ([]byte, error) { return nil, errors.New("secret") }); err == nil || strings.Contains(err.Error(), "secret") {
		t.Fatal(err)
	}
}
func TestMacInstallOpensOnlyVendorPage(t *testing.T) {
	a := fakeTailscale(t, "darwin")
	a.Lookup = func(name string) (string, error) {
		if name != "open" {
			t.Fatal(name)
		}
		return "/usr/bin/open", nil
	}
	a.Run = func(_ context.Context, s process.Spec, _ *os.File, _ func([]byte)) ([]byte, int, error) {
		if strings.Join(s.Args, " ") != "https://tailscale.com/download/mac" {
			t.Fatal(s)
		}
		return nil, 0, nil
	}
	// Opening a page is not installation evidence.
	if err := a.Install(context.Background(), nil); err == nil {
		t.Fatal("false installation success")
	}
}

func TestExistingOfficialRepositoryIsReused(t *testing.T) {
	a := aptFixture(t)
	read := a.ReadFile
	key, err := os.CreateTemp(t.TempDir(), "key")
	if err != nil {
		t.Fatal(err)
	}
	key.Close()
	info, _ := os.Stat(key.Name())
	a.ReadFile = func(path string) ([]byte, error) {
		if strings.HasSuffix(path, "tailscale.list") {
			return []byte("# official\n" + repositorySource("https://pkgs.tailscale.com/stable/ubuntu/resolute")), nil
		}
		return read(path)
	}
	a.Stat = func(path string) (os.FileInfo, error) {
		if strings.HasSuffix(path, ".gpg") {
			return info, nil
		}
		return nil, os.ErrNotExist
	}
	if plan := a.Installation(); plan.Kind != "apt-existing" {
		t.Fatal(plan)
	}
	calls := 0
	a.Run = func(_ context.Context, s process.Spec, _ *os.File, _ func([]byte)) ([]byte, int, error) {
		calls++
		if s.Args[2] != "/usr/bin/apt-get" || !strings.Contains(strings.Join(s.Args, " "), "AllowUnauthenticated=false") {
			t.Fatal(s)
		}
		return nil, 0, nil
	}
	err = a.install(context.Background(), nil, func(context.Context, string) ([]byte, error) {
		t.Fatal("existing repository downloaded again")
		return nil, nil
	})
	if err != nil || calls != 2 {
		t.Fatal(calls, err)
	}
}
