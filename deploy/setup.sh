#!/usr/bin/env bash
# One-time server setup for an Oracle Cloud Ubuntu VM (Always Free, ARM).
#
#   curl -fsSL https://raw.githubusercontent.com/sanjeev200009/investment_AI/main/deploy/setup.sh | bash
#
# Installs Docker, opens ports 80/443 in the VM's own firewall, clones the repo
# into ~/investment_AI and writes deploy/.env. It does NOT copy secrets: after it
# finishes, upload investai-backend/.env and firebase-key.json (see deploy/README.md).
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/sanjeev200009/investment_AI.git}"
APP_DIR="$HOME/investment_AI"

echo "==> Installing Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

echo "==> Opening ports 80 and 443 in the VM firewall"
# Oracle's Ubuntu images ship iptables rules that drop everything except SSH,
# even after the cloud security list allows the port.
for port in 80 443; do
  if ! sudo iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport "$port" -j ACCEPT
  fi
done
sudo apt-get install -y netfilter-persistent >/dev/null
sudo netfilter-persistent save

echo "==> Getting the code"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$APP_DIR"
fi

echo "==> Writing deploy/.env"
PUBLIC_IP="$(curl -fsS https://api.ipify.org)"
DOMAIN_DEFAULT="$(echo "$PUBLIC_IP" | tr . -).sslip.io"
if [ ! -f "$APP_DIR/deploy/.env" ]; then
  FLOWER_PASS="$(openssl rand -hex 12)"
  cat > "$APP_DIR/deploy/.env" <<EOF
DOMAIN=$DOMAIN_DEFAULT
FLOWER_BASIC_AUTH=admin:$FLOWER_PASS
EOF
  echo "    Flower login: admin / $FLOWER_PASS (saved in deploy/.env)"
fi

cat <<EOF

Done. Your API address will be:  https://$DOMAIN_DEFAULT/api/v1

Next, from your own computer, upload the two secret files:
  scp investai-backend/.env              ubuntu@$PUBLIC_IP:~/investment_AI/investai-backend/.env
  scp investai-backend/firebase-key.json ubuntu@$PUBLIC_IP:~/investment_AI/investai-backend/firebase-key.json

Then on this server (log out and back in first, for the docker group):
  cd ~/investment_AI/deploy && docker compose up -d --build
EOF
