# E0.B installation and platform decisions

Primary sources checked 2026-09-21. These are mechanism decisions, not claims that
installation, macOS or Windows/WSL runtime acceptance occurred.

## Linux

The [official stable package index](https://pkgs.tailscale.com/stable/) publishes
per-distribution repository instructions. The [Linux installation guide](https://tailscale.com/docs/install/linux)
also offers the vendor shell installer. E0.B chooses structured package-manager
commands and never executes a downloaded shell script.

Automatic assistance is limited to these published APT combinations:

| Distribution | Releases accepted by Blaine |
| --- | --- |
| Ubuntu | 22.04 jammy, 24.04 noble, 25.10 questing, 26.04 resolute |
| Debian | 11 bullseye, 12 bookworm, 13 trixie |

Existing Tailscale always wins: connect first checks its status and never upgrades,
reinstalls or reauthenticates a ready installation. If the binary is absent,
Blaine reuses an exact official repository/key pair or offers fresh repository
setup. Different/partial files are a manual-review boundary, not an overwrite.

Fresh setup fetches the public key at
`https://pkgs.tailscale.com/stable/<distro>/<release>.noarmor.gpg` over verified
HTTPS (no redirects, 20-second/64-KiB limit). Trust bootstrap follows the vendor's
HTTPS distribution mechanism; a packet-header/size check is only format screening,
not an independent signature/fingerprint claim. Generated source:

```text
deb [signed-by=/usr/share/keyrings/tailscale-archive-keyring.gpg] https://pkgs.tailscale.com/stable/<distro> <release> main
```

The key is installed with mode 0644 under `/usr/share/keyrings`, and the source at
`/etc/apt/sources.list.d/tailscale.list`. Then APT update/install verifies signed
metadata/package integrity with insecure/unauthenticated allowances explicitly
false. `systemctl start tailscaled` is added only when systemd is detected. Other
init systems receive service diagnostics if package setup did not start the daemon.
Blaine never invokes a standalone daemon itself. Commands use absolute executable
paths and argv, each elevated separately through `sudo -k --`. The sudo dialog
uses its own terminal; no timestamp authorization or operator grant is retained.
A failed package transaction can leave OS state requiring package-manager repair.

Fedora/RHEL-family DNF, openSUSE Zypper, Arch pacman and Alpine apk are represented
by vendor package guidance, not automatic adapters. The official index documents
DNF repository setup/install and Zypper repository refresh/install; distro/version
and DNF4/DNF5 differences need isolated fixtures/live acceptance before automation.
Unknown derivatives/releases do not inherit Debian/Ubuntu automation from ID_LIKE.
No tarball, third-party binary, headless daemon or installer-script fallback exists.

Authentication runs `tailscale up --timeout=3m` as the existing user, with no reset,
force-reauth, auth key or settings changes supplied. If the daemon denies that user,
an administrator must perform ordinary native onboarding (`sudo tailscale up`)
outside Blaine. This respects the request's restriction of client-driven elevation
to installation/service setup. Existing operator privileges are neither assumed
nor changed. The [vendor CLI contract](https://tailscale.com/docs/reference/tailscale-cli)
defines normal CLI operation and separate operator configuration.

## macOS

Prefer the signed Standalone app from the [vendor download](https://tailscale.com/download/mac)
and [native installation guide](https://tailscale.com/docs/install/mac). The
[variant comparison](https://tailscale.com/docs/concepts/macos-variants) distinguishes
Standalone, Mac App Store and the separate open-source daemon. No variant migration
is automated and no existing app is replaced.

The [macOS CLI documentation](https://tailscale.com/docs/reference/tailscale-cli?tab=macos)
locates the CLI at `/Applications/Tailscale.app/Contents/MacOS/Tailscale` and
specifies `TAILSCALE_BE_CLI=1` for scripted use. Blaine sets that only on the status
child so doctor cannot accidentally launch the GUI. App existence, executable CLI,
status availability, login and readiness remain separate observations. PATH-only
CLI without a known native app is an ownership-review condition, even if its daemon
responds. A failed native status command cannot distinguish every OS approval/socket
failure; guidance names VPN/system-extension authorization without claiming a
specific permission dialog was observed.

After confirmation, missing app opens the fixed official HTTPS download page.
Installed/logged-out app opens `/Applications/Tailscale.app` with `/usr/bin/open`
resolved through the platform boundary, then polls status for at most three
minutes. Installer signature approval, VPN/system-extension permission and browser
login remain visible OS/vendor actions. No artifact is downloaded by Blaine on Mac;
Apple's native installer/Gatekeeper retains signature enforcement.

The [Homebrew cask](https://formulae.brew.sh/cask/tailscale-app) currently uses
`brew install --cask tailscale-app` and distributes the vendor macOS package. It is
an optional user-managed package route, not invoked by Blaine. The
[vendor daemon documentation](https://github.com/tailscale/tailscale/wiki/Tailscaled-on-macOS)
also describes `brew install --formula tailscale`; that is a different daemon
ownership model, deliberately outside this native-app onboarding implementation.

macOS is designed, fixture-tested and cross-built for amd64/arm64. App/CLI layouts,
OS dialogs, native authentication and runtime behavior have **not** been live-tested.

## Windows + WSL2

[Tailscale's WSL guidance](https://tailscale.com/docs/install/windows/wsl2) recommends
Windows-host ownership and warns against simultaneously running both daemons.
The [Windows installation guide](https://tailscale.com/docs/install/windows) provides
the native installer and login journey. Blaine directs the human there; it does
not run a Windows installer through unverified interop.

[Microsoft interop documentation](https://learn.microsoft.com/en-us/windows/wsl/filesystems)
permits `.exe` invocation but also permits disabling it. [WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)
can disable Windows PATH import and change automount locations. Therefore E0.B
uses PATH lookup for `tailscale.exe`, no guessed `/mnt/c` or profile path. A missing
executable means **host availability unknown**, not proof of uninstallation.
A responding native CLI provides host status only. A responding guest CLI/daemon
alongside it is a topology conflict; neither daemon is changed.

The [networking documentation](https://learn.microsoft.com/en-us/windows/wsl/networking)
describes NAT and mirrored modes. Neither native host status nor a config file
proves a guest tailnet route. The [version commands](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)
are part of the future live spike, including encoding/localization and selected
distro verification. This implementation does not parse unverified Windows output
or invent reliable host discovery from a fixed drive mount.

**Affected-platform STOP:** no WSL workstation was available. Host ownership/reuse
cannot be certified; `wsl_host_reuse` remains UNKNOWN and connect cannot return
network readiness for WSL, even with a connected Windows host. Bounded host CLI
inspection/guidance is implemented, but automatic Windows discovery outside PATH,
WSL2 version proof, guest route/DNS tests and native authentication orchestration
remain unverified. No nested-daemon alternative is exposed in this slice.

The [current JetBrains ACP help](https://www.jetbrains.com/help/ai-assistant/acp.html)
lists WSL as unsupported. That is a separate E0.E IDE gate; it does not block
network investigation. No IntelliJ configuration is implemented here.
