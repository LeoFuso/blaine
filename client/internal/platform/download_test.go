package platform

import (
	"bytes"
	"context"
	"io"
	"net/http"
	"strings"
	"testing"
)

type roundTrip func(*http.Request) (*http.Response, error)

func (f roundTrip) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }
func TestVendorKeyOriginLimitsAndRedirect(t *testing.T) {
	original := http.DefaultTransport
	t.Cleanup(func() { http.DefaultTransport = original })
	key := append([]byte{0x99}, bytes.Repeat([]byte{1}, 200)...)
	for _, tc := range []struct {
		name   string
		status int
		body   []byte
		want   bool
	}{
		{"vendor key", 200, key, true}, {"not found", 404, []byte("secret"), false}, {"oversized", 200, bytes.Repeat([]byte{0x99}, 65537), false}, {"html", 200, bytes.Repeat([]byte("x"), 200), false}, {"redirect", 302, nil, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			calls := 0
			http.DefaultTransport = roundTrip(func(r *http.Request) (*http.Response, error) {
				calls++
				if r.URL.Host != "pkgs.tailscale.com" {
					t.Fatal("redirect followed")
				}
				return &http.Response{StatusCode: tc.status, Body: io.NopCloser(bytes.NewReader(tc.body)), Header: http.Header{"Location": []string{"https://evil.example/secret"}}, Request: r}, nil
			})
			data, err := vendorKey(context.Background(), "https://pkgs.tailscale.com/stable/ubuntu/resolute.noarmor.gpg")
			if (err == nil) != tc.want || calls != 1 {
				t.Fatal(err, calls)
			}
			if !tc.want && (data != nil || strings.Contains(err.Error(), "secret")) {
				t.Fatal("untrusted data escaped")
			}
		})
	}
	http.DefaultTransport = roundTrip(func(*http.Request) (*http.Response, error) { t.Fatal("untrusted origin fetched"); return nil, nil })
	for _, url := range []string{"http://pkgs.tailscale.com/stable/x.noarmor.gpg", "https://evil.example/stable/x.noarmor.gpg", "https://pkgs.tailscale.com/other"} {
		if _, err := vendorKey(context.Background(), url); err == nil {
			t.Fatal(url)
		}
	}
}
