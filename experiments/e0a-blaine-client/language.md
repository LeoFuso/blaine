# E0.A language/build decision

Go selected before substantial implementation. ADR 0022 leaves language open;
Hub Q1 recommends Go for this separate workstation boundary. No contradictory
canonical client was found: `runtime/personal_acp.py` and its shell/venv launcher
are server-side D2, not a portable workstation installation.

Go was absent from PATH and standard toolchain locations on this host. Downloaded
the official Go 1.27.1 linux/amd64 archive into `/tmp`, verified SHA-256
`63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445`, and unpacked under
`/tmp/blaine-e0a-toolchain`. No system install. Initial sandbox DNS was unavailable;
the scoped toolchain download succeeded with approved network access. This is
build-tool acquisition, not client networking.

Sources: [official archive metadata](https://go.dev/dl/?mode=json),
[installation](https://go.dev/doc/install), [process API](https://pkg.go.dev/os/exec).
The standard library supplies JSON, explicit argv execution without a shell,
context cancellation and direct stdio descriptors. Linux/WSL and macOS share POSIX
process groups; platform detection/paths stay in one small package. CGO-disabled
binaries and normal cross-compilation meet the low runtime dependency target.
No third-party Go modules, CLI framework, ACP SDK or language benchmark is needed.
The module declares Go 1.23 as its language floor; validation uses exactly 1.27.1,
not an untested claim about every older toolchain.

Use immediate process-group termination for disposable transport resources on
cancellation; preserve ordinary child exit codes. This primitive is not workspace
execution or Task cancellation. Helpers must not daemonize/escape their process
group; stronger hostile-process containment belongs to future E2 provider gates.
