package wire

import (
	"bytes"
	"strings"
	"testing"
)

func TestACPFramingAndCorrelation(t *testing.T) {
	s := NewSession()
	input := "{\"jsonrpc\":\"2.0\",\"id\":7,\"method\":\"session/prompt\",\"params\":{}}\r\n"
	var out bytes.Buffer
	if e := s.Forward(strings.NewReader(input), &out, 0); e != nil || out.String() != input {
		t.Fatal("request bytes changed", e)
	}
	reply := "{\"jsonrpc\":\"2.0\",\"id\":7,\"result\":{}}\n"
	out.Reset()
	if e := s.Forward(strings.NewReader(reply), &out, 1); e != nil || out.String() != reply {
		t.Fatal("response bytes changed", e)
	}
	if e := s.Validate([]byte(reply), 1); e == nil {
		t.Fatal("accepted duplicate response")
	}
}
func TestACPRejectsBeforeForward(t *testing.T) {
	cases := []string{"banner\n", `{"jsonrpc":"2.0","jsonrpc":"2.0","method":"hello"}` + "\n", `{"jsonrpc":"2.0","id":1,"result":{}}` + "\n", `{"jsonrpc":"2.0","method":"hello"}`, strings.Repeat(" ", Limit+1) + "\n", `{"jsonrpc":"2.0","method":"session/new","params":{"mcpServers":[{"name":"untrusted"}]}}` + "\n"}
	for _, line := range cases {
		var out bytes.Buffer
		if e := NewSession().Forward(strings.NewReader(line), &out, 0); e == nil || out.Len() != 0 {
			t.Fatal("bad frame reached consumer")
		}
	}
	for _, method := range []string{"fs/read_text_file", "fs/write_text_file", "terminal/create", "session/request_permission", "unknown/extension"} {
		var out bytes.Buffer
		line := `{"jsonrpc":"2.0","id":2,"method":"` + method + `","params":{}}` + "\n"
		if e := NewSession().Forward(strings.NewReader(line), &out, 1); e == nil || out.Len() != 0 {
			t.Fatal("host capability acquired authority")
		}
	}
}
func TestInitializeDropsCapabilities(t *testing.T) {
	var out bytes.Buffer
	line := `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{"fs":{"readTextFile":true},"terminal":true}}}` + "\n"
	if e := NewSession().Forward(strings.NewReader(line), &out, 0); e != nil {
		t.Fatal(e)
	}
	if strings.Contains(out.String(), "readTextFile") || strings.Contains(out.String(), "terminal") {
		t.Fatal("capability leaked")
	}
}
func TestStrictJSON(t *testing.T) {
	for _, input := range []string{`{"a":{"x":1,"x":2}}`, `{} {}`, "{\"a\":\"\xff\"}", strings.Repeat("[", 65) + strings.Repeat("]", 65)} {
		var out any
		if Decode([]byte(input), &out) == nil {
			t.Fatal("accepted ambiguous JSON")
		}
	}
}
