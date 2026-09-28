# Deploying InvestAI on an Oracle Cloud Always Free VM

Everything the proposal specifies runs on one free server:

```
Oracle VM (Ubuntu, ARM, 2 CPU / 12 GB)  ── Docker Compose
 ├── caddy    HTTPS on 443, certificate from Let's Encrypt
 ├── api      FastAPI  (migrations run on start)
 ├── worker   Celery worker
 ├── beat     Celery Beat (schedule in celery_worker.py, Asia/Colombo)
 ├── flower   Celery monitoring (private, SSH tunnel only)
 └── redis    Celery broker
Supabase (free)  ── Postgres + Auth
Firebase (free)  ── push notifications (Android)
Brevo (free)     ── OTP and reset emails
```

## 1. Create the VM (Oracle console, ~15 min)

1. Sign up at cloud.oracle.com (card check, Always Free resources are not charged).
2. **Compute → Instances → Create instance**
   - Image: **Canonical Ubuntu 24.04**
   - Shape: **Ampere VM.Standard.A1.Flex**, 2 OCPU, 12 GB (the Always Free limit)
   - Networking: keep "Assign a public IPv4 address"
   - SSH keys: "Generate a key pair" and **download the private key**
   - If it says "Out of capacity", try another availability domain or retry later.
3. **Open ports 80 and 443**: instance → Subnet → Default Security List →
   Add Ingress Rules → Source `0.0.0.0/0`, TCP, destination ports `80,443`.
4. Note the instance's **public IP**.

## 2. Set up the server (~5 min)

From PowerShell on your computer (use the key you downloaded):

```powershell
ssh -i C:\path\to\ssh-key.key ubuntu@<PUBLIC_IP>
```

On the server:

```bash
curl -fsSL https://raw.githubusercontent.com/sanjeev200009/investment_AI/main/deploy/setup.sh | bash
```

It installs Docker, opens the VM firewall, clones the repo and prints your API
address, `https://<ip-with-dashes>.sslip.io/api/v1`, and a Flower password.

## 3. Upload the two secret files

From PowerShell on your computer, in the repo folder:

```powershell
scp -i C:\path\to\ssh-key.key investai-backend\.env ubuntu@<PUBLIC_IP>:~/investment_AI/investai-backend/.env
```

```powershell
scp -i C:\path\to\ssh-key.key investai-backend\investai-33294-firebase-adminsdk-fbsvc-0ca0ee510d.json ubuntu@<PUBLIC_IP>:~/investment_AI/investai-backend/firebase-key.json
```

## 4. Start everything

On the server (log out and back in once after setup, so `docker` works without sudo):

```bash
cd ~/investment_AI/deploy && docker compose up -d --build
```

Check it:

```bash
docker compose ps                      # all services "running" / api "healthy"
curl https://$(grep DOMAIN .env | cut -d= -f2)/health
docker compose logs -f beat worker     # watch jobs fire (market hours: 9:00–14:59 Colombo)
```

Flower (task history, failures): `ssh -i <key> -L 5555:localhost:5555 ubuntu@<PUBLIC_IP>`,
then open http://localhost:5555 and log in with the password from `deploy/.env`.

## 5. Updating after a code change

```bash
cd ~/investment_AI && git pull && cd deploy && docker compose up -d --build
```

## 6. Android app with push notifications

1. **Firebase console → project `investai-33294` → Add app → Android**,
   package name `lk.investai.mobile`. Download `google-services.json` into
   `investai-mobile/` (it is gitignored).
2. Free account at expo.dev, then in `investai-mobile/`:

   ```powershell
   npm install -g eas-cli
   ```

   ```powershell
   eas login
   ```

   ```powershell
   eas init
   ```

   ```powershell
   eas env:create --name EXPO_PUBLIC_API_BASE_URL --value https://<ip-with-dashes>.sslip.io/api/v1 --environment preview --visibility plaintext
   ```

   ```powershell
   eas env:create --name GOOGLE_SERVICES_JSON --type file --value ./google-services.json --environment preview --visibility secret
   ```

   ```powershell
   eas build --platform android --profile preview
   ```

3. Install the APK from the link EAS prints on an Android phone (not Expo Go),
   sign in, and allow notifications when asked.

## End-to-end acceptance test

| # | Do this | Expect |
|---|---|---|
| 1 | Register in the app | OTP email arrives (Brevo) |
| 2 | Enter the code, then sign in | Home loads with ASPI and market data |
| 3 | Ask the AI "What is the price of JKH?" | Answer streams in, quoting a real price and date |
| 4 | Add a holding and a watchlist stock | Both persist after restarting the app |
| 5 | Create a rule, e.g. `price_above` at a price just under the current one, during market hours | Within 15 min a push notification arrives and the Alerts tab shows it |
| 6 | `docker compose logs beat` | Entries every 15 min in market hours, every 30 min for news |
