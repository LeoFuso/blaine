package process

import (
	"os"
	"os/exec"
	"testing"
)

func TestForegroundTerminalAndRestoration(t *testing.T) {
	python, err := exec.LookPath("python3")
	if err != nil {
		t.Skip("python3 required for isolated PTY fixture")
	}
	// The PTY is isolated; no sudo, credentials, installation or real terminal.
	script := `
import os,pty,select,sys,time
pid,fd=pty.fork()
if pid==0:
 os.execv(sys.argv[1],[sys.argv[1],'-test.run=TestHelperProcess','--','--process-helper',sys.argv[2]])
data=b''
try:
 deadline=time.monotonic()+5
 answered=False
 while time.monotonic()<deadline:
  if not select.select([fd],[],[],0.1)[0]: continue
  try: part=os.read(fd,4096)
  except OSError: break
  if not part: break
  data+=part
  if b'TTY_PROMPT' in data and not answered:
   os.write(fd,b'fixture-answer\n');answered=True
  if b'FOREGROUND_PASS' in data: break
 assert b'FOREGROUND_PASS' in data,repr(data)
 _,status=os.waitpid(pid,0)
 assert status==0,status
finally:
 try: os.kill(pid,9)
 except ProcessLookupError: pass
 os.close(fd)
`
	for _, mode := range []string{"foreground-parent", "foreground-cancel"} {
		command := exec.Command(python, "-c", script, os.Args[0], mode)
		if out, err := command.CombinedOutput(); err != nil {
			t.Fatalf("%s: %v: %s", mode, err, out)
		}
	}
}
