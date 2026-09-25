#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workspace="${GOUDA_WORKSPACE:-$(python3 - "$repo" <<'PY'
import sys
from pathlib import Path
repo=Path(sys.argv[1]).resolve()
print(repo.parent.parent if repo.name == 'tsukuba-autonomous-robot' and repo.parent.name == 'src' else Path.home()/'gouda_ws')
PY
)}"
access="$workspace/bags/gouda/phone-access"
config="$access/phone-access.json"
for file in "$workspace/install/setup.bash" "$config"; do
  [[ -r "$file" ]] || { echo "Required file is missing or unreadable: $file" >&2; exit 1; }
done
[[ -r /opt/ros/jazzy/setup.bash ]] || { echo 'ROS 2 Jazzy setup was not found.' >&2; exit 1; }
python3 - "$config" <<'PY'
import json, os, sys
from pathlib import Path
config=json.loads(Path(sys.argv[1]).read_text())
args=config.get('gateway_arguments')
if not isinstance(args,list) or not args or any(not isinstance(v,str) for v in args):
    raise SystemExit('phone-access.json must contain a nonempty gateway_arguments string array')
for name in ('tls_cert','tls_key','remote_token_file'):
    value=config.get(name)
    if not isinstance(value,str) or not Path(value).is_file() or not os.access(value,os.R_OK):
        raise SystemExit(f'phone-access.json has a missing or unreadable {name}')
if not any(args[i] == '--allowed-host' for i in range(len(args))):
    raise SystemExit('phone-access.json must pass explicit --allowed-host values')
PY
chmod 600 "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["tls_key"])' "$config")" \
          "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["remote_token_file"])' "$config")"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
wrapper_dir="$HOME/.local/libexec"
unit="$unit_dir/gouda-phone-gateway.service"
wrapper="$wrapper_dir/gouda-phone-gateway"
[[ ! -e "$unit" ]] || { echo "Refusing to overwrite existing unit: $unit" >&2; exit 1; }
[[ ! -e "$wrapper" ]] || { echo "Refusing to overwrite existing wrapper: $wrapper" >&2; exit 1; }
mkdir -p "$unit_dir" "$wrapper_dir"
python3 - "$wrapper" "$workspace" "$config" <<'PY'
import shlex, sys
from pathlib import Path
wrapper, workspace, config = map(Path, sys.argv[1:])
code = "import json,os,sys; c=json.load(open(sys.argv[1])); args=c['gateway_arguments']; os.execvpe('ros2',['ros2','run','gouda_gui','phone_gateway',*args],dict(os.environ))"
body = "#!/usr/bin/env bash\nset -euo pipefail\nexport GOUDA_WORKSPACE="+shlex.quote(str(workspace))+"\nsource /opt/ros/jazzy/setup.bash\nsource "+shlex.quote(str(workspace/'install/setup.bash'))+"\nexec python3 -c "+shlex.quote(code)+" "+shlex.quote(str(config))+"\n"
wrapper.write_text(body)
wrapper.chmod(0o700)
PY
cat > "$unit" <<'UNIT'
[Unit]
Description=Gouda phone field gateway
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=%h/.local/libexec/gouda-phone-gateway
Restart=always
RestartSec=3
UMask=0077

[Install]
WantedBy=default.target
UNIT
systemctl --user daemon-reload
systemctl --user enable --now gouda-phone-gateway.service
printf 'Installed and started user service: %s\n' "$unit"
printf 'Check with: systemctl --user status gouda-phone-gateway.service\n'
printf 'For startup before login, separately run: sudo loginctl enable-linger "$(id -un)"\n'
