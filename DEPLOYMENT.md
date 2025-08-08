# Deployment Guide

This guide covers different deployment options for the Slack GPT Bot.

## 🐳 Docker Deployment (Recommended)

### Prerequisites
- Docker
- Docker Compose

### Quick Start
```bash
# 1. Configure environment variables
cp env.example .env
# Edit .env with your actual values

# 2. Deploy using the deployment script
./deploy.sh

# 3. Check status
docker-compose ps
docker-compose logs -f
```

### Manual Deployment
```bash
# Build and start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker-compose logs -f
```

## ☸️ Kubernetes Deployment

### Prerequisites
- Kubernetes cluster
- kubectl configured
- Helm (optional)

### Deploy to Kubernetes

1. **Create secrets** (replace with your actual values):
```bash
# Encode your secrets
echo -n "your-openai-api-key" | base64
echo -n "your-openai-assistant-id" | base64
echo -n "your-slack-bot-token" | base64
echo -n "your-slack-signing-secret" | base64

# Update kubernetes/secrets.yaml with the encoded values
kubectl apply -f kubernetes/secrets.yaml
```

2. **Deploy the application**:
```bash
kubectl apply -f kubernetes/deployment.yaml
```

3. **Set up ingress** (optional):
```bash
# Update kubernetes/ingress.yaml with your domain
kubectl apply -f kubernetes/ingress.yaml
```

### Kubernetes Commands
```bash
# Check deployment status
kubectl get pods
kubectl get services

# View logs
kubectl logs -f deployment/slack-gpt-bot

# Scale deployment
kubectl scale deployment slack-gpt-bot --replicas=3

# Delete deployment
kubectl delete -f kubernetes/
```

## 🚀 Cloud Platform Deployment

### Heroku
```bash
# Install Heroku CLI
# Create app
heroku create your-slack-bot

# Set environment variables
heroku config:set OPENAI_API_KEY=your-key
heroku config:set OPENAI_ASSISTANT_ID=your-assistant-id
heroku config:set SLACK_BOT_TOKEN=your-token
heroku config:set SLACK_SIGNING_SECRET=your-secret

# Deploy
git push heroku main
```

### Google Cloud Run
```bash
# Build and deploy
gcloud builds submit --tag gcr.io/PROJECT_ID/slack-bot
gcloud run deploy slack-bot \
  --image gcr.io/PROJECT_ID/slack-bot \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="OPENAI_API_KEY=your-key,OPENAI_ASSISTANT_ID=your-id"
```

### AWS ECS
```bash
# Build and push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
docker build -t slack-bot .
docker tag slack-bot:latest ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/slack-bot:latest
docker push ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/slack-bot:latest

# Deploy to ECS (use AWS Console or CLI)
```

## 🔧 Environment Configuration

### Required Environment Variables
```bash
OPENAI_API_KEY=sk-...
OPENAI_ASSISTANT_ID=asst_...
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=your-signing-secret
HOST=0.0.0.0
PORT=8000
```

### Health Check
The application provides a health check endpoint:
```
GET /health
```

## 📊 Monitoring

### Docker Compose
```bash
# View logs
docker-compose logs -f

# Check resource usage
docker stats

# Restart service
docker-compose restart
```

### Kubernetes
```bash
# View logs
kubectl logs -f deployment/slack-gpt-bot

# Check resource usage
kubectl top pods

# Monitor events
kubectl get events
```

## 🔒 Security Considerations

1. **Environment Variables**: Never commit `.env` files to version control
2. **Secrets Management**: Use Kubernetes secrets or cloud platform secret management
3. **Network Security**: Configure firewalls and network policies
4. **SSL/TLS**: Use HTTPS in production
5. **Rate Limiting**: Consider implementing rate limiting for the API endpoints

## 🚨 Troubleshooting

### Common Issues

1. **Service not responding**:
   ```bash
   # Check if service is running
   curl http://localhost:8000/health
   
   # Check logs
   docker-compose logs
   ```

2. **Memory not persisting**:
   - Ensure volume mounts are configured correctly
   - Check file permissions for `thread_memory.json`

3. **Slack webhook errors**:
   - Verify Slack signature verification
   - Check webhook URL configuration
   - Ensure bot has proper permissions

4. **OpenAI API errors**:
   - Verify API key is correct
   - Check assistant ID exists
   - Monitor API usage limits

### Debug Commands
```bash
# Test environment variables
python3 -c "from app import app; print('App loaded successfully')"

# Test OpenAI connection
python3 -c "import openai; print('OpenAI SDK loaded')"

# Check memory file
cat thread_memory.json
```

## 📈 Scaling

### Horizontal Scaling (Kubernetes)
```bash
# Scale to 3 replicas
kubectl scale deployment slack-gpt-bot --replicas=3

# Auto-scaling
kubectl autoscale deployment slack-gpt-bot --cpu-percent=70 --min=2 --max=10
```

### Load Balancing
- Use Kubernetes LoadBalancer service
- Configure ingress with SSL termination
- Set up monitoring and alerting

## 🔄 Updates and Rollbacks

### Docker Compose
```bash
# Update
docker-compose pull
docker-compose up -d

# Rollback
docker-compose down
docker-compose up -d --force-recreate
```

### Kubernetes
```bash
# Update
kubectl set image deployment/slack-gpt-bot slack-bot=new-image:tag

# Rollback
kubectl rollout undo deployment/slack-gpt-bot
```

## 📝 Logging

The application logs to stdout/stderr. Configure log aggregation for production:

- **Docker**: Use log drivers
- **Kubernetes**: Use Fluentd or similar
- **Cloud**: Use platform-specific logging services 