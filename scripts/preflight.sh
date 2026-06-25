#!/usr/bin/env bash
set -euo pipefail

mask() {
  sed -E \
    -e 's#[0-9]{6,}:[A-Za-z0-9_-]{20,}#***REDACTED***#g' \
    -e 's#(TG_TOKEN|BOT_TOKEN|TELEGRAM_BOT_TOKEN|YOOMONEY_TOKEN)[[:space:]]*=[[:space:]]*[^[:space:]]+#\1=***REDACTED***#g' \
    -e 's#(CRYPTOMUS|YOOKASSA|SECRET|PASSWORD)[[:space:]]*([:=])[[:space:]]*[^[:space:]]+#\1\2***REDACTED***#gI' \
    -e 's#-----BEGIN (RSA|OPENSSH) PRIVATE KEY-----#***REDACTED***#g'
}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: not a git repository" | mask
  exit 1
fi

if [[ ! -f docker-compose.yml ]]; then
  echo "ERROR: docker-compose.yml not found" | mask
  exit 1
fi

if git ls-files --error-unmatch bot/.env >/dev/null 2>&1; then
  echo "ERROR: bot/.env is tracked by git" | mask
  exit 2
fi

hits_file=".artifacts/preflight_secrets.txt"
mkdir -p .artifacts
: > "$hits_file"

while IFS= read -r -d '' f; do
  if ! grep -Iq . "$f"; then
    continue
  fi
  perl -ne '
    chomp(my $line = $_);
    if ($line =~ /[0-9]{6,}:[A-Za-z0-9_-]{20,}/ ||
        $line =~ /BEGIN (RSA|OPENSSH) PRIVATE KEY/) {
      print "$ARGV:$.:$line\n";
      next;
    }
    next unless $line =~ /^\s*(?:-\s*)?[A-Za-z0-9_]*(?:TOKEN|SECRET|PASSWORD|KEY)[A-Za-z0-9_]*\s*[:=]/;
    my $value = $line;
    $value =~ s/^[^:=]*[:=]\s*//;
    $value =~ s/\s+#.*$//;
    $value =~ s/^\s+|\s+$//g;
    my $lower = lc $value;
    next if $lower eq "" ||
      $lower eq "change_me" ||
      $lower eq "changeme" ||
      $lower eq "define_me" ||
      $lower eq "define me!";
    next if $value =~ /^<[^>]+>$/ ||
      $value =~ /^\$\{[A-Za-z0-9_]+:-?[Cc][Hh][Aa][Nn][Gg][Ee][Mm][Ee]\}$/;
    print "$ARGV:$.:$line\n" if length($value) >= 8 && $value =~ /^[A-Za-z0-9_.\/+=:\@-]+$/;
  ' "$f" >> "$hits_file" 2>/dev/null || true
done < <(git ls-files -z)

if [[ -s "$hits_file" ]]; then
  echo "ERROR: potential secrets found in tracked files:" | mask
  cat "$hits_file" | mask
  exit 2
fi

# --- Dependency vulnerability scan ---
if command -v pip-audit >/dev/null 2>&1; then
  echo "preflight: running pip-audit..." | mask
  audit_file=".artifacts/preflight_audit.txt"
  if pip-audit -r bot/requirements.txt --desc --progress-spinner off > "$audit_file" 2>&1; then
    echo "preflight: pip-audit ok (0 vulnerabilities)" | mask
  else
    echo "WARNING: pip-audit found vulnerabilities:" | mask
    cat "$audit_file" | mask
  fi
else
  echo "preflight: pip-audit not installed, skipping vulnerability scan" | mask
fi

echo "preflight: ok" | mask
exit 0
