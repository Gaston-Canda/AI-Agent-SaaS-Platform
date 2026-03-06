# AWS Deployment Guide

## Topology options

1. Single-node (EC2 + Docker Compose)
2. Multi-node (ECS Fargate + RDS + ElastiCache + ALB)

## Option A: EC2 (single node)

### 1. Provision
- Ubuntu 22.04 EC2 instance
- Security groups:
  - 80/443 for frontend
  - 8000 internally behind reverse proxy (optional)
  - 22 for SSH (restricted)

### 2. Install runtime
- Docker Engine + Docker Compose plugin
- AWS CLI (optional for pulling from ECR)

### 3. Pull and run
- Copy `deploy/aws/ec2-docker-compose.yml` to server
- Create `.env` with production values
- Run:

```bash
docker compose -f ec2-docker-compose.yml up -d
```

## Option B: ECS Fargate (recommended for scale)

### Components
- API service (task definition: `ecs-task-definition-api.json`)
- Worker service (task definition: `ecs-task-definition-worker.json`)
- PostgreSQL: Amazon RDS (PostgreSQL)
- Redis broker/backend: ElastiCache Redis
- Load balancer: ALB -> API tasks
- Frontend: S3 + CloudFront or ECS nginx service

### Notes
- Store secrets in SSM Parameter Store or Secrets Manager
- Attach CloudWatch log groups for api/worker streams
- Configure ECS service auto-scaling by CPU and request count

## Load balancer recommendations
- ALB target group health path: `/api/health`
- Health check interval: 15s
- Healthy threshold: 2
- Unhealthy threshold: 3

## Production hardening checklist
- Use TLS termination at ALB/CloudFront
- Restrict RDS/Redis network access to VPC subnets
- Enable RDS automated backups + multi-AZ
- Enable Redis snapshot/persistence policy
- Use least-privilege IAM task roles
