# Deploy with Helm

Use Helm to deploy Smart Intersection to a Kubernetes cluster.
This guide will help you:

- Add the Helm chart repository.
- Configure the Helm chart to match your deployment needs.
- Deploy and verify the application.

Helm simplifies Kubernetes deployments by streamlining configurations and
enabling easy scaling and updates. For more details, see
[Helm Documentation](https://helm.sh/docs/).

## Prerequisites

Before You Begin, ensure the following:

- **Kubernetes Cluster**: Ensure you have a properly installed and
configured Kubernetes cluster.
- **System Requirements**: Verify that your system meets the [minimum requirements](./system-requirements.md).
- **Tools Installed**: Install the required tools:
  - Kubernetes CLI (kubectl)
  - Helm 3 or later
- **Storage Provisioner**: A default storage class is required for persistent volumes

## Steps to Deploy

To deploy the Smart Intersection Sample Application, copy and paste the entire block of following commands into your terminal and run them:


### Step 1: Clone the Repository

Before you can deploy with Helm, you must clone the repository:

```bash
# Clone the repository
git clone https://github.com/open-edge-platform/edge-ai-suites.git

# Navigate to the Metro AI Suite directory
cd edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/
```

### Step 2: Configure Proxy Settings (If behind a proxy)

If you are deploying in a proxy environment, update the values.yaml file with your proxy settings before installation:

```bash
# Edit the values.yml file to add proxy configuration
nano ./smart-intersection/chart/values.yaml
```

Update the existing proxy configuration in your values.yaml with following values:

```yaml
http_proxy: "http://your-proxy-server:port"
https_proxy: "http://your-proxy-server:port"
no_proxy: "localhost,127.0.0.1,.local,.cluster.local"
```

Replace `your-proxy-server:port` with your actual proxy server details.



### Step 3: Setup Storage (If Needed, for single node clusters)

Check if your cluster has a default storage class:

```bash
kubectl get storageclass
```

If no storage class exists or none is marked as `(default)`, install one:

```bash
# Install local-path-provisioner for single-node clusters
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

### Step 4: Deploy the application

Now you're ready to deploy the Smart Intersection application with nginx reverse proxy and self-signed certificates:

```bash
# Install the chart (works on both single-node and multi-node clusters)
helm upgrade --install smart-intersection ./smart-intersection/chart \
  --create-namespace \
  --set grafana.service.type=NodePort \
  --set global.storageClassName="" \
  -n smart-intersection

# Wait for all pods to be ready
kubectl wait --for=condition=ready pod --all -n smart-intersection --timeout=300s
```

> **Note**: Using `global.storageClassName=""` makes the deployment use whatever default storage class exists on your cluster. This works for both single-node and multi-node setups.

> **Note**: The application now uses self-signed certificates generated directly in Kubernetes secrets, providing HTTPS access without requiring cert-manager. This eliminates webhook validation issues and simplifies deployment.

## Access Application Services

The Smart Intersection application provides multiple access methods, similar to the Docker Compose setup:

### Nginx Reverse Proxy Access (HTTPS - Recommended)

All services are accessible through the nginx reverse proxy with TLS encryption using self-signed certificates:

- **Smart Intersection (Main UI)**: `https://<HOST_IP>:30443/` - Fully functional
- **Grafana Dashboard**: `https://<HOST_IP>:30443/grafana/` - Fully functional  
- **NodeRED Editor**: `https://<HOST_IP>:30443/nodered/` - Fully functional
- **DL Streamer API**: `https://<HOST_IP>:30443/api/pipelines/` - Fully functional

> **Security Note**: The application uses self-signed certificates for HTTPS. Your browser will show a security warning when first accessing the site. Click "Advanced" and "Proceed to site" (or equivalent) to continue. This is safe for local deployments.

### Direct Service Access

Additional services provide direct access on dedicated ports:

- **InfluxDB**: `http://<HOST_IP>:30086/` - Full database functionality and web UI

### Service Credentials

#### Smart Intersection Web UI
- **Username**: `admin`
- **Password**: Get from secrets:
  ```bash
  kubectl get secret smart-intersection-supass-secret -n smart-intersection -o jsonpath='{.data.supass}' | base64 -d && echo
  ```

#### Grafana Dashboard  
- **Username**: `admin`
- **Password**: `admin`

#### InfluxDB (Direct Access for Login)
- **Access**: Use direct access on port 30086 for login and full functionality
- **URL**: `http://<HOST_IP>:30086/`
- **Username**: `admin`
- **Password**: Get from secrets:
  ```bash
  kubectl get secret smart-intersection-influxdb-secrets -n smart-intersection -o jsonpath='{.data.influxdb2-admin-password}' | base64 -d && echo
  ```

#### NodeRED Editor
- **No login required** - Visual programming interface

#### DL Streamer Pipeline Server
- **API Access**: No authentication required for status endpoints

> **Note**: For InfluxDB, use the direct access on port 30086 (`http://<HOST_IP>:30086/`) for login and full functionality. The proxy access through nginx (`https://<HOST_IP>:30443/influxdb/`) provides basic functionality and API access but is not recommended for the web UI login.

## Uninstall the Application

To uninstall the application, run the following command:

```bash
helm uninstall smart-intersection -n smart-intersection
```

## Delete the Namespace

To delete the namespace and all resources within it, run the following command:

```bash
kubectl delete namespace smart-intersection
```

## Complete Cleanup

If you want to completely remove all infrastructure components installed during the setup process:

```bash
# Remove local-path-provisioner (if installed)
kubectl delete -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml

# Delete all PVCs in the smart-intersection namespace
kubectl delete pvc --all -n smart-intersection

# Delete any remaining PVs (persistent volumes)
kubectl delete pv --all

# Force cleanup of stuck PVCs if needed (patch each PVC individually)
kubectl get pvc -n smart-intersection --no-headers | awk '{print $1}' | xargs -I {} kubectl patch pvc {} -n smart-intersection --type merge -p '{"metadata":{"finalizers":null}}'

# Remove additional storage classes (if created)
kubectl delete storageclass hostpath local-storage standard
```

> **Note**: This complete cleanup will remove storage provisioning from your cluster. You'll need to reinstall the storage provisioner for future deployments that require persistent volumes.

## Troubleshooting

### 403 Forbidden Error on Login

If you encounter a 403 Forbidden error when trying to log in, this is typically a CSRF (Cross-Site Request Forgery) protection issue. The web service startup script should automatically configure the CSRF trusted origins, but if issues persist:

1. **Check the web pod logs**:
   ```bash
   kubectl logs -l app=smart-intersection-web -n smart-intersection --tail=20
   ```

2. **Restart the web service**:
   ```bash
   kubectl rollout restart deployment smart-intersection-web -n smart-intersection
   ```

3. **Verify CSRF configuration**:
   ```bash
   kubectl exec -l app=smart-intersection-web -n smart-intersection -- grep -A10 "CSRF_TRUSTED_ORIGINS" /home/scenescape/SceneScape/manager/settings.py
   ```

### Cameras Showing as Offline

If cameras appear offline in the UI:

1. **Check all pods are running**:
   ```bash
   kubectl get pods -n smart-intersection
   ```

2. **Verify scene service is running**:
   ```bash
   kubectl logs -l app=smart-intersection-scene -n smart-intersection --tail=20
   ```

3. **Check DL Streamer pipeline server**:
   ```bash
   kubectl logs -l app=smart-intersection-dlstreamer-pipeline-server -n smart-intersection --tail=20
   ```

4. **Restart scene service if needed**:
   ```bash
   kubectl rollout restart deployment smart-intersection-scene -n smart-intersection
   ```

### Database Connection Issues

If services fail to connect to the database:

1. **Check database pod status**:
   ```bash
   kubectl get pods -l app=smart-intersection-pgserver -n smart-intersection
   ```

2. **Reset database if needed** (this will remove all data):
   ```bash
   kubectl scale deployment smart-intersection-pgserver --replicas=0 -n smart-intersection
   kubectl delete pvc smart-intersection-pgserver-db -n smart-intersection
   kubectl scale deployment smart-intersection-pgserver --replicas=1 -n smart-intersection
   ```

## What to Do Next

- **[Troubleshooting Helm Deployments](./support.md#troubleshooting-helm-deployments)**: Consolidated troubleshooting steps for resolving issues during Helm deployments.
- **[Get Started](./get-started.md)**: Ensure you have completed the initial setup steps before proceeding.

## Supporting Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/home/)
- [Helm Documentation](https://helm.sh/docs/)
