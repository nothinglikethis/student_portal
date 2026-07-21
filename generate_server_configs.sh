#!/bin/bash

# Determine current directory and user
PROJECT_DIR="$PWD"
USER_NAME="$USER"

# 1. Create gunicorn.service
cat <<EOF > gunicorn.service
[Unit]
Description=gunicorn daemon
After=network.target

[Service]
User=$USER_NAME
Group=www-data
WorkingDirectory=$PROJECT_DIR
ExecStart="$PROJECT_DIR/venv/bin/python" -m gunicorn --access-logfile - --workers 3 --bind "unix:$PROJECT_DIR/gunicorn.sock" admission_project.wsgi:application

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Generated gunicorn.service"

# 2. Create nginx_admissions.conf
cat <<EOF > nginx_admissions.conf
server {
    listen 80;
    server_name _;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        alias "$PROJECT_DIR/staticfiles/";
    }

    location / {
        include proxy_params;
        proxy_pass "http://unix:$PROJECT_DIR/gunicorn.sock";
    }
}
EOF

echo "✅ Generated nginx_admissions.conf"

# 3. Echo the required deployment commands in green
GREEN='\033[1;32m'
NC='\033[0m' # No Color

echo -e "\n${GREEN}=====================================================${NC}"
echo -e "${GREEN}Server configuration files generated successfully!${NC}"
echo -e "${GREEN}Please run the following sudo commands to deploy:${NC}"
echo -e "${GREEN}=====================================================${NC}\n"

echo -e "${GREEN}sudo cp gunicorn.service /etc/systemd/system/${NC}"
echo -e "${GREEN}sudo cp nginx_admissions.conf /etc/nginx/sites-available/${NC}"
echo -e "${GREEN}sudo ln -sf /etc/nginx/sites-available/nginx_admissions.conf /etc/nginx/sites-enabled/${NC}"
echo -e "${GREEN}sudo rm -f /etc/nginx/sites-enabled/default${NC}"
echo -e "${GREEN}sudo systemctl daemon-reload${NC}"
echo -e "${GREEN}sudo systemctl start gunicorn${NC}"
echo -e "${GREEN}sudo systemctl enable gunicorn${NC}"
echo -e "${GREEN}sudo systemctl restart nginx${NC}"
echo -e "\n${GREEN}=====================================================${NC}"
