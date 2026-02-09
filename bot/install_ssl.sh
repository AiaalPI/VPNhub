#chmod +x install_ssl.sh
# sudo ./install_ssl.sh mydomain.ru

set -e

if [ -z "$1" ]; then
    echo "Использование: $0 <your-domain>"
    exit 1
fi

DOMAIN=$1
NGINX_CONF="/etc/nginx/sites-available/$DOMAIN.conf"

echo "=== Обновление пакетов ==="
apt update -y

echo "=== Установка nginx ==="
apt install -y nginx

echo "=== Создание конфига Nginx для домена $DOMAIN ==="

cat > $NGINX_CONF <<EOF
server {
    listen 80;
    listen [::]:80;

    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8888;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

echo "=== Активируем конфиг ==="
ln -sf $NGINX_CONF /etc/nginx/sites-enabled/$DOMAIN.conf

echo "=== Проверяем конфиг Nginx ==="
nginx -t

echo "=== Перезапуск Nginx ==="
systemctl reload nginx

echo "=== Установка Certbot ==="
apt install -y certbot python3-certbot-nginx

echo "=== Запрашиваем SSL сертификат для $DOMAIN ==="
certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN

echo "=== Проверка автообновления сертификатов ==="
systemctl status certbot.timer --no-pager

echo "=== Готово! ==="
echo "SSL установлен, Nginx настроен, автообновление сертификатов включено."
echo "Теперь твой домен доступен по HTTPS."
