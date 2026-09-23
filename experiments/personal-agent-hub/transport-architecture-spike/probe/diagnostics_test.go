package main

import (
	"encoding/json"
	"errors"
	"net"
	"strings"
	"testing"
)

func TestDiagnosticErrorsDoNotExposeRawMaterial(t *testing.T) {
	secret := "private-material-must-not-be-emitted"
	for _, err := range []error{
		errors.New(secret),
		&net.DNSError{Err: secret, Name: secret, Server: secret, IsNotFound: true},
		&net.OpError{Op: secret, Net: secret, Err: errors.New(secret)},
	} {
		b, e := json.Marshal(dialFailure(err))
		if e != nil || strings.Contains(string(b), secret) {
			t.Fatal("diagnostic error contains private material")
		}
	}
	if dialFailure(&net.DNSError{IsNotFound: true})["kind"] != "dns" {
		t.Fatal("DNS failure was not distinguished")
	}
}
