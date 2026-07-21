#!/bin/bash

# Parul Admissions System - Startup & Diagnostic Script

GREEN='\033[1;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Parul Admissions System Startup Check${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo -e "${GREEN}[1/3] Checking PostgreSQL Database...${NC}"
sudo systemctl status postgresql --no-pager | grep "Active:" || echo "Warning: PostgreSQL does not appear to be active."

echo -e "\n${GREEN}[2/3] Restarting Gunicorn Daemon...${NC}"
sudo systemctl restart gunicorn
sudo systemctl status gunicorn --no-pager | grep "Active:" || echo "Warning: Gunicorn failed to start."

echo -e "\n${GREEN}[3/3] Restarting Nginx Server...${NC}"
sudo systemctl restart nginx
sudo systemctl status nginx --no-pager | grep "Active:" || echo "Warning: Nginx failed to start."

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ All services have been refreshed!${NC}"
echo -e "You can access the portal at: http://localhost/"
echo -e "${GREEN}========================================${NC}"
