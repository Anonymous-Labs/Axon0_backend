# Production Deployment Guide
## AXON - Universal Memory Layer

This guide provides step-by-step instructions for deploying AXON to production for commercial use.

---

## 🎯 Pre-Deployment Checklist

### Security
- [ ] All secrets are set via environment variables
- [ ] Strong SECRET_KEY and JWT_SECRET_KEY (minimum 32 characters)
- [ ] Database credentials are secure
- [ ] Redis password is set
- [ ] CORS origins are configured correctly
- [ ] SSL/TLS certificates are configured
- [ ] Security headers are enabled

### Configuration
- [ ] Environment variables are set
- [ ] Database is configured (PostgreSQL recommended)
- [ ] Redis is configured
- [ ] Gemini API key is set (if using AI features)
- [ ] Frontend API URL is configured

### Infrastructure
- [ ] Docker and Docker Compose are installed
- [ ] Domain name is configured
- [ ] SSL certificates are obtained
- [ ] Backup strategy is in place
- [ ] Monitoring is set up

---

## 🚀 Deployment Steps

### 1. Server Setup

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. Clone and Configure

```bash
# Clone repository (assuming backend and frontend are in separate repos or monorepo)
# If monorepo:
git clone <your-repo-url>
cd Axon0_backend

# If separate repos, clone both:
# git clone <backend-repo-url> Axon0_backend
# git clone <frontend-repo-url> Axon0_Frontend
# cd Axon0_backend

# Create environment files
cp .env.example .env
# If frontend is in sibling directory:
cp ../Axon0_Frontend/.env.example ../Axon0_Frontend/.env

# Edit environment files with your values
nano .env
nano ../Axon0_Frontend/.env
```

### 3. Generate Secrets

```bash
# Generate secure secrets
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('DB_PASSWORD=' + secrets.token_urlsafe(24))"
python3 -c "import secrets; print('REDIS_PASSWORD=' + secrets.token_urlsafe(24))"
```

### 4. Configure Environment Variables

Edit `.env` (in backend directory):

```env
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<generated-secret-key>
JWT_SECRET_KEY=<generated-jwt-secret>
DATABASE_URL=postgresql+asyncpg://axon_user:<db-password>@db:5432/axon_db
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
GEMINI_API_KEY=<your-gemini-key>
```

Edit `../Axon0_Frontend/.env`:

```env
VITE_API_BASE_URL=https://api.yourdomain.com
VITE_ENVIRONMENT=production
VITE_ENABLE_LOGGING=false
```

### 5. Create Production Environment File

Create `.env.production` in the backend directory:

```env
# Database
DB_PASSWORD=<your-db-password>

# Redis
REDIS_PASSWORD=<your-redis-password>

# API Base URL
API_BASE_URL=https://api.yourdomain.com

# Allowed Origins
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### 6. Build and Deploy

```bash
# Make sure you're in the backend directory
cd Axon0_backend

# Build and start services
docker-compose -f docker-compose.prod.yml --env-file .env.production up -d --build

# Check logs
docker-compose -f docker-compose.prod.yml logs -f

# Check health
curl http://localhost/health
```

### 7. Initialize Database

```bash
# Run migrations (if using Alembic)
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Or tables will be created automatically on first run
```

### 8. Verify Deployment

```bash
# Check all services are running
docker-compose -f docker-compose.prod.yml ps

# Test backend health
curl http://localhost/health/db
curl http://localhost/health/redis

# Test frontend
curl http://localhost/health
```

---

## 🔒 Security Hardening

### 1. SSL/TLS Configuration

```bash
# Obtain SSL certificate (Let's Encrypt)
sudo apt-get install certbot
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Copy certificates to nginx/ssl/
mkdir -p ./nginx/ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ./nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ./nginx/ssl/key.pem
sudo chmod 644 ./nginx/ssl/cert.pem
sudo chmod 600 ./nginx/ssl/key.pem
```

### 2. Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 80/tcp  # HTTP
sudo ufw allow 443/tcp # HTTPS
sudo ufw enable
```

### 3. Database Security

- Use strong passwords
- Restrict database access to backend container only
- Enable SSL for database connections
- Regular backups

### 4. Redis Security

- Set strong password
- Bind to localhost only
- Disable dangerous commands

---

## 📊 Monitoring

### Health Checks

- `GET /health` - Basic health
- `GET /health/db` - Database health
- `GET /health/redis` - Redis health
- `GET /health/full` - Full health check

### Metrics (Admin Only)

- `GET /api/v1/metrics` - Application metrics

### Logging

- All logs are in JSON format
- Logs are output to stdout (capture with Docker)
- Use log aggregation service (e.g., ELK, CloudWatch)

---

## 🔄 Maintenance

### Backup Database

```bash
# Backup PostgreSQL
docker-compose -f docker-compose.prod.yml exec db pg_dump -U axon_user axon_db > backup_$(date +%Y%m%d).sql

# Restore
docker-compose -f docker-compose.prod.yml exec -T db psql -U axon_user axon_db < backup_20240101.sql
```

### Update Application

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose -f docker-compose.prod.yml up -d --build

# Run migrations if needed
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### View Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend
```

---

## 🚨 Troubleshooting

### Service Won't Start

1. Check logs: `docker-compose -f docker-compose.prod.yml logs`
2. Verify environment variables
3. Check database connection
4. Verify Redis connection

### Database Connection Issues

1. Check database is running: `docker-compose -f docker-compose.prod.yml ps db`
2. Verify DATABASE_URL in .env
3. Check database logs: `docker-compose -f docker-compose.prod.yml logs db`

### Redis Connection Issues

1. Check Redis is running
2. Verify REDIS_URL and password
3. Test connection: `docker-compose -f docker-compose.prod.yml exec redis redis-cli ping`

### Frontend Not Loading

1. Check frontend container: `docker-compose -f docker-compose.prod.yml ps frontend`
2. Verify VITE_API_BASE_URL
3. Check browser console for errors
4. Verify CORS settings

---

## 📈 Scaling

### Horizontal Scaling

```yaml
# In docker-compose.prod.yml, scale backend
docker-compose -f docker-compose.prod.yml up -d --scale backend=3
```

### Load Balancer

Use Nginx or cloud load balancer in front of multiple backend instances.

### Database Scaling

- Use PostgreSQL read replicas for read-heavy workloads
- Consider connection pooling
- Monitor query performance

---

## 🔐 Security Best Practices

1. **Never commit secrets** to version control
2. **Use strong passwords** (minimum 32 characters for secrets)
3. **Enable HTTPS** in production
4. **Regular security updates** for dependencies
5. **Monitor logs** for suspicious activity
6. **Regular backups** of database
7. **Limit API access** with rate limiting
8. **Use environment-specific configs**
9. **Enable security headers**
10. **Regular dependency updates**

---

## 📞 Support

For production issues:
1. Check logs first
2. Review health endpoints
3. Check metrics endpoint
4. Review this guide
5. Contact support if needed

---

**Last Updated:** 2024  
**Version:** 1.0.0

