package process

import (
	"context"
	"errors"
	"os"
	"strings"
	"testing"
	"time"
)

func TestCaptureBoundedAndLiteral(t *testing.T) {
	var observed strings.Builder
	data, code, err := Capture(context.Background(), helperSpec("argv", "literal $(id); token"), nil, func(chunk []byte) { observed.Write(chunk) })
	if err != nil || code != 0 || string(data) != "literal $(id); token\n" || observed.String() != string(data) {
		t.Fatal(code, err)
	}
	_, code, err = Capture(context.Background(), helperSpec("argv", strings.Repeat("x", 64000), strings.Repeat("y", 64000)), nil, nil)
	if code != 0 || err != nil {
		t.Fatal(code, err)
	}
	args := make([]string, 20)
	for i := range args {
		args[i] = strings.Repeat("x", 60000)
	}
	data, _, err = Capture(context.Background(), helperSpec("argv", args...), nil, nil)
	if err == nil || data != nil {
		t.Fatal("oversized output accepted")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Millisecond)
	defer cancel()
	_, _, err = Capture(ctx, helperSpec("stubborn"), nil, nil)
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatal(err)
	}
}
func TestForegroundRefusesNonTerminal(t *testing.T) {
	input, err := os.Open(os.DevNull)
	if err != nil {
		t.Fatal(err)
	}
	defer input.Close()
	if IsTerminal(input) {
		t.Fatal("null is not a terminal")
	}
	s := helperSpec("argv", "never launched")
	s.Foreground = true
	_, code, err := Capture(context.Background(), s, input, nil)
	if code == 0 || err == nil {
		t.Fatal("nonterminal accepted")
	}
}

func TestChildEnvironmentOverride(t *testing.T) {
	t.Setenv("BLAINE_TEST_CHILD_MODE", "parent")
	spec := helperSpec("environment")
	spec.Env = []string{"BLAINE_TEST_CHILD_MODE=child"}
	data, code, err := Capture(context.Background(), spec, nil, nil)
	if err != nil || code != 0 || string(data) != "child\n" || os.Getenv("BLAINE_TEST_CHILD_MODE") != "parent" {
		t.Fatal(code, err, string(data))
	}
}
