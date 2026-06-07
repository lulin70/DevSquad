# DevSquad Helm Chart

Kubernetes Helm Chart for deploying **DevSquad V3.6.0** - Multi-Role AI Task Orchestrator.

## Quick Start

### Prerequisites

- Kubernetes 1.23+
- Helm 3.0+
- PVC storage class (for SQLite/checkpoints persistence)

### Install

```bash
# Add repository (if applicable)
# helm repo add devsquad https://github.com/lulin70/DevSquad/charts

# Install with default values
helm install devsquad ./helm/devsquad

# Install with custom API key
helm install devsquad ./helm/devsquad \
  --set envVars.OPENAI_API_KEY=sk-xxx \
  --set envVars.LLM_BACKEND=openai

# Install with custom resources
helm install devsquad ./helm/devsquad \
  --set resources.requests.cpu=1000m \
  --set resources.requests.memory=1Gi \
  --set resources.limits.cpu=4000m \
  --set resources.limits.memory=4Gi
```

### Access Services

```bash
# Port forward API server
kubectl port-forward svc/devsquad-api 8000:8000

# Access Swagger UI: http://localhost:8000/docs
# Access ReDoc: http://localhost:8000/redoc

# Port forward Dashboard (if enabled)
kubectl port-forward svc/devsquad-dashboard 8501:8501

# Access Dashboard: http://localhost:8501
```

## Configuration

### Key Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `1` |
| `image.repository` | Container image name | `devsquad` |
| `image.tag` | Container image tag | `3.6.0` |
| `service.type` | Service type (ClusterIP/NodePort/LoadBalancer) | `ClusterIP` |
| `service.port` | API service port | `8000` |
| `dashboard.enabled` | Enable Streamlit dashboard | `true` |
| `dashboard.port` | Dashboard port | `8501` |
| `persistence.enabled` | Enable persistent storage | `true` |
| `persistence.size` | Storage size | `10Gi` |

### Environment Variables

Configure LLM backend and other settings via `envVars`:

```yaml
envVars:
  LLM_BACKEND: "mock"           # mock, openai, anthropic
  LOG_LEVEL: "WARNING"          # DEBUG, INFO, WARNING, ERROR
  OPENAI_API_KEY: ""            # Your OpenAI API key
  OPENAI_BASE_URL: ""           # Custom OpenAI endpoint
  OPENAI_MODEL: "gpt-4"         # Model name
  ANTHROPIC_API_KEY: ""         # Anthropic API key
  ANTHROPIC_MODEL: "claude-sonnet-4-20250514"
```

### Resource Management

```yaml
resources:
  requests:
    cpu: "500m"
    memory: "512Mi"
  limits:
    cpu: "2000m"
    memory: "2Gi"
```

### Ingress Configuration

Enable Ingress for external access:

```yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt
  hosts:
    - host: devsquad.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: devsquad-tls
      hosts:
        - devsquad.example.com
```

## Custom Values File

Create a custom `values-custom.yaml`:

```yaml
replicaCount: 2

image:
  repository: your-registry/devsquad
  tag: "3.6.0"
  pullPolicy: Always

envVars:
  LLM_BACKEND: openai
  OPENAI_API_KEY: ""

resources:
  requests:
    cpu: "1000m"
    memory: "1Gi"
  limits:
    cpu: "4000m"
    memory: "4Gi"

persistence:
  enabled: true
  size: 20Gi
  storageClass: fast-ssd

nodeSelector:
  node-type: gpu

tolerations:
  - key: "nvidia.com/gpu"
    operator: "Exists"
    effect: "NoSchedule"
```

Install with custom values:

```bash
helm install devsquad ./helm/devsquad -f values-custom.yaml
```

## Upgrade

```bash
# Upgrade with new values
helm upgrade devsquad ./helm/devsquad \
  --set envVars.OPENAI_API_KEY=new-key

# Upgrade with values file
helm upgrade devsquad ./helm/devsquad -f values-custom.yaml

# Rollback to previous version
helm rollback devsquad 1
```

## Uninstall

```bash
helm uninstall devsquad
```

## Monitoring & Debugging

```bash
# Check pod status
kubectl get pods -l app.kubernetes.io/name=devsquad

# View logs
kubectl logs -f deployment/devsquad

# Describe pod for troubleshooting
kubectl describe pod -l app.kubernetes.io/name=devsquad

# Exec into container
kubectl exec -it deployment/devsquad -- /bin/bash
```

## Architecture

```
┌─────────────────────────────────────────┐
│            Kubernetes Cluster           │
│                                         │
│  ┌──────────────┐  ┌────────────────┐  │
│  │   Ingress     │  │   Service       │  │
│  │  (Optional)  │→ │  (ClusterIP)    │  │
│  └──────────────┘  └───────┬────────┘  │
│                            │           │
│  ┌─────────────────────────▼────────┐  │
│  │         Deployment               │  │
│  │  ┌───────────────────────────┐   │  │
│  │  │ DevSquad Container        │   │  │
│  │  │ ├─ API Server (:8000)     │   │  │
│  │  │ ├─ Dashboard (:8501)      │   │  │
│  │  │ └─ Volume Mount (/data)   │   │  │
│  │  └───────────────────────────┘   │  │
│  └─────────────────┬───────────────┘  │
│                    │                   │
│  ┌─────────────────▼───────────────┐  │
│  │ PersistentVolumeClaim (10Gi)    │  │
│  │ - SQLite database               │  │
│  │ - Checkpoint files              │  │
│  │ - Config files                  │  │
│  └─────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## Security Notes

- **API Keys**: Never store API keys in values.yaml. Use Kubernetes Secrets or external secret management.
- **Network Policies**: Consider adding NetworkPolicies to restrict pod communication.
- **RBAC**: The chart creates minimal RBAC permissions by default.
- **Pod Security**: Runs as non-root user (UID 1000) by default.

## Support

- **Issues**: [GitHub Issues](https://github.com/lulin70/DevSquad/issues)
- **Documentation**: [GUIDE_EN.md](../../docs/i18n/GUIDE_EN.md)
- **Version**: DevSquad V3.6.0

## License

MIT License - see [LICENSE](../../LICENSE)
