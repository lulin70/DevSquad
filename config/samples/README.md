# DevSquad Production Configuration Samples
# ======================================
#
# This directory contains production-ready configuration samples
# for deploying DevSquad in a production environment.
#
# Files:
#   - nginx.conf          : Nginx reverse proxy configuration
#   - devsquad-api.service : Systemd service file for API server
#   - devsquad-dashboard.service : Systemd service for Dashboard
#   - env.production     : Environment variables template
#
# Usage:
#   1. Copy files to appropriate locations:
#      sudo cp nginx.conf /etc/nginx/sites-available/devsquad
#      sudo ln -s /etc/nginx/sites-available/devsquad /etc/nginx/sites-enabled/
#      sudo cp devsquad-api.service /etc/systemd/system/
#      sudo cp devsquad-dashboard.service /etc/systemd/system/
#
#   2. Edit configuration files to match your environment:
#      - Update domain names in nginx.conf
#      - Update paths in systemd service files
#      - Set API keys and secrets in env.production
#
#   3. Enable and start services:
#      sudo systemctl daemon-reload
#      sudo systemctl enable devsquad-api
#      sudo systemctl start devsquad-api
#      sudo systemctl enable devsquad-dashboard
#      sudo systemctl start devsquad-dashboard
#      sudo systemctl reload nginx
#
# Security Notes:
#   - Always use HTTPS in production (SSL/TLS certificates required)
#   - Change default passwords before deployment
#   - Use environment variables or secret managers for sensitive data
#   - Configure firewall rules (ufw/iptables) to restrict access
#   - Enable rate limiting on nginx (see nginx.conf)
#   - Regularly update dependencies: pip install -U fastapi uvicorn streamlit
#
# Monitoring:
#   - Check logs: journalctl -u devsquad-api -f
#   - Health check: curl https://your-domain.com/api/v1/health
#   - Metrics: curl https://your-domain.com/api/v1/metrics/current
#
# For questions, see:
#   - INSTALL.md (Installation Guide)
#   - docs/USAGE_GUIDE.md (Usage Guide)
#   - config/deployment.yaml (Deployment Configuration)
#
# Version: V3.6.0-Prod
# Last Updated: 2026-05-03
