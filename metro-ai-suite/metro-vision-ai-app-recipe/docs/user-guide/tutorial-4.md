# Crowd Analytics System Tutorial

<!--
**Sample Description**: This tutorial demonstrates how to build an intelligent crowd analytics system using edge AI technologies for real-time vehicle detection, license plate recognition, and vehicle attribute analysis.


This tutorial walks you through creating an AI-powered tolling system that automatically detects vehicles, recognizes license plates, and analyzes vehicle attributes in real-time. The system leverages Intel's DLStreamer framework with pre-trained AI models to process video streams from toll booth cameras, enabling automated toll collection and traffic monitoring.
-->

<!--
**What You Can Do**: This guide covers the complete development workflow for building a Crowd Analytics system.
-->

By following this guide, you will learn how to:
- **Set up the Crowd Analytics Application**: Create a new application based on the Smart Parking template and configure it for crowd analytics use cases
- **Download and Configure AI Models**: Install YOLO object detection models
- **Configure Video Processing Pipeline**: Set up the DLStreamer pipeline (for real-time vehicle detection and license plate recognition)
- **Deploy and Run the System**: Launch the containerized application and monitor its performance

## Prerequisites

- Verify that your system meets the [minimum system requirements](./system-requirements.md) for running edge AI applications
- Install Docker: [Docker Installation Guide](https://docs.docker.com/get-docker/)
- Enable running Docker without "sudo": [Post-installation steps for Linux](https://docs.docker.com/engine/install/linux-postinstall/)
- Ensure you have at least 8GB of available disk space for AI models and video files
- Basic understanding of containerized applications and video processing concepts

## Application Architecture Overview

<!--
**Architecture Image Placeholder**: Add architecture diagram showing the flow from video input through AI models to toll processing output
-->
![Crowd Analytics System Diagram](_images/ai-tolling-system.svg)


The Crowd Analytics system consists of several key components:
<!--
- **Video Input**: Processes live camera feeds or video files from toll booth cameras
- **Object Detection**: Uses YOLOv10s model to detect vehicles in the video stream
- **License Plate Recognition**: Employs Intel's specialized model to extract license plate text
- **Vehicle Attributes**: Analyzes vehicle type, color, and other characteristics
- **Data Processing**: Aggregates results for toll calculation and traffic monitoring
-->
## Set up and First Use

### 1. **Create the Crowd Analytics Application Directory**

Navigate to the metro vision AI recipe directory and create the AI tolling application by copying the Smart Parking template:

```bash
cd ./edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe
cp -r smart-parking/ crowd-analytics/
```

This creates a new `crowd-analytics` directory with all the necessary application structure and configuration files.

### 2. **Download Sample Video File**

Download a sample video file containing vehicle traffic for testing the AI tolling system:
<!--
```bash
mkdir -p ./crowd-analytics/src/dlstreamer-pipeline-server/videos/
wget -O ./crowd-analytics/src/dlstreamer-pipeline-server/videos/cars_extended.mp4 \
  https://github.com/open-edge-platform/edge-ai-resources/raw/refs/heads/main/videos/cars_extended.mp4
```

<details>
<summary>
Video File Details
</summary>

The sample video contains:
- Multiple vehicles passing through a toll booth scenario
- Various vehicle types (cars, trucks)
- Clear license plate visibility for testing recognition accuracy
- Duration: Approximately 5 minutes of footage
- Resolution: 640x360

</details>
-->
### 3. **Download and Setup AI Models**

Create and run the model download script to install all required AI models:

```bash
docker run --rm --user=root \
  -e http_proxy -e https_proxy -e no_proxy \
  -v "$PWD:/home/dlstreamer/metro-suite" \
  intel/dlstreamer:2025.0.1.3-ubuntu24 bash -c "$(cat <<EOF

cd /home/dlstreamer/metro-suite/

mkdir -p crowd-analytics/src/dlstreamer-pipeline-server/models/public
export MODELS_PATH=/home/dlstreamer/metro-suite/crowd-analytics/src/dlstreamer-pipeline-server/models
/home/dlstreamer/dlstreamer/samples/download_public_models.sh yolov10s

mkdir -p crowd-analytics/src/dlstreamer-pipeline-server/models/intel

python3 -m pip install openvino-dev[onnx,tensorflow2]

echo "Fix ownership..."
chown -R "$(id -u):$(id -g)" crowd-analytics/src/dlstreamer-pipeline-server/models crowd-analytics/src/dlstreamer-pipeline-server/videos 2>/dev/null || true
EOF
)"

```

The installation script downloads three essential AI models:

| **Model Name** | **Purpose** | **Framework** | **Size** |
|----------------|-------------|---------------|----------|
| YOLOv10s | Vehicle detection and tracking | PyTorch/OpenVINO | ~20MB |

<details>
<summary>
Model Download Process Details
</summary>

The installation script performs the following operations:
1. Creates the required directory structure under `src/dlstreamer-pipeline-server/models/`
2. Runs a DLStreamer container to access model download tools
3. Downloads public YOLO models using the built-in download scripts
<!--
4. Uses OpenVINO Model Zoo downloader for Intel-optimized models
-->
5. Downloads corresponding model configuration files for proper inference
6. Sets up proper file permissions for container access

Expected download time: 5-10 minutes depending on internet connection.

</details>

### 4. **Configure the AI Processing Pipeline**

Update the pipeline configuration to use the _________ AI models. Create or update the configuration file:

```bash
cat > ./crowd-analytics/src/dlstreamer-pipeline-server/config.json << 'EOF'
{
    "config": {
        "logging": {
            "C_LOG_LEVEL": "INFO",
            "PY_LOG_LEVEL": "INFO"
        },
        "cert_type": [
            "zmq"
        ],
        "pipelines": [
            {
                "name": "yolov10_1_cpu",
                "source": "gstreamer",
                "queue_maxsize": 50,
                "pipeline": "{auto_source} name=source ! decodebin ! gvadetect model=/home/pipeline-server/models/public/yolov10s/FP32/yolov10s.xml pre-process-backend=opencv threshold=0.7 model-instance-id=inst0 name=detection ! queue ! gvaclassify model=/home/pipeline-server/models/colorcls2/colorcls2.xml model_proc=/home/pipeline-server/models/colorcls2/colorcls2.json pre-process-backend=opencv model-instance-id=inst1 name=classification ! queue ! gvapython module=/home/pipeline-server/models/colorcls2/process class=Process function=process_frame ! queue ! gvawatermark ! gvametaconvert add-empty-results=true name=metaconvert ! gvafpscounter ! appsink name=destination",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "detection-properties": {
                            "element": {
                                "name": "detection",
                                "format": "element-properties"
                            }
                        },
                        "detection-device": {
                            "element": {
                                "name": "detection",
                                "property": "device"
                            },
                            "type": "string",
                            "default": "{env[DETECTION_DEVICE]}"
                        }
                    }
                },
                "auto_start": false,
                "publish_frame": true
            }
        ]
    }
}
EOF
```
<!--
<details>
<summary>
Pipeline Configuration Explanation
</summary>

The GStreamer pipeline configuration defines the AI processing workflow:

- **Source**: Accepts video input from files or live streams
- **Decode**: Converts video format to raw frames for processing
- **gvadetect**: Runs YOLO object detection to identify vehicles
- **gvaclassify (1st)**: Applies license plate recognition model to detected vehicles
- **gvaclassify (2nd)**: Analyzes vehicle attributes (type, color, etc.)
- **gvawatermark**: Adds visual annotations to processed frames
- **gvametaconvert**: Converts inference results to structured metadata
- **gvametapublish**: Publishes results to external systems
- **gvafpscounter**: Monitors processing performance

Each element can be configured for different hardware targets (CPU, GPU, VPU).

</details>
-->
### 5. **Configure Application Environment**

Update the environment configuration to use the Crowd Analytics application:

```bash
# Update the .env file to specify the crowd-analytics application and HOST IP Address
sed -i 's/^SAMPLE_APP=.*/SAMPLE_APP=crowd-analytics/' .env
sed -i "s/^HOST_IP=.*/HOST_IP=$(hostname -I | cut -f1 -d' ')/" .env


# Create self signed certificate for nginx
mkdir -p src/nginx/ssl
cd crowd-analytics/src/nginx/ssl
if [ ! -f server.key ] || [ ! -f server.crt ]; then
    echo "Generate self-signed certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout server.key -out server.crt -subj "/C=US/ST=CA/L=San Francisco/O=Intel/OU=Edge AI/CN=localhost"
    chown -R "$(id -u):$(id -g)" server.key server.crt 2>/dev/null || true

fi

# Verify the configuration
grep SAMPLE_APP= .env
grep HOST_IP= .env
```

Expected output: `SAMPLE_APP=crowd-analytics`

### 6. **Deploy the Application**

Set up the Docker Compose configuration and start the application:

```bash
# Copy the compose file for deployment
cp compose-without-scenescape.yml docker-compose.yml

# Start all services in detached mode
docker compose up -d
```

The deployment process will:
- Pull required container images
- Start the DLStreamer pipeline server
- Initialize the Node-RED flow management
- Launch the Grafana dashboard
- Set up the MQTT message broker

## Validation and Expected Results

### 1. **Verify Service Status**

Check that all services are running correctly:

```bash
docker ps
```

Expected output should show containers for:
- `dlstreamer-pipeline-server`
- `node-red`
- `grafana`
- `mosquitto` (MQTT broker)

### 2. **Access the Application Interface**

Open your web browser and navigate to:
- **Main Dashboard**: `https://localhost/grafana` (Grafana)
    - Username: admin
    - Password: admin
- **Node-RED Flow Editor**: `https://localhost/nodered/`

### 3. **Test Video Processing**

Start the AI pipeline and process the sample video:

```bash
# Start the crowd analytics pipeline with the sample video
curl -k -s https://localhost/api/pipelines/user_defined_pipelines/yolov10_1_cpu -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/new_video_1.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_detection_1",
            "timeout": 1000
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_detection_1"
        }
    },
    "parameters": {
        "detection-device": "CPU"
    }
}'
```

### 4. **View Live Video Stream**

Access the processed video stream with AI annotations through WebRTC:

```bash
# Open in your web browser (replace <HOST_IP> with your actual IP address)
# For local testing, typically use localhost or 127.0.0.1
http://<HOST_IP>:8889/object_detection_1
```

For local testing, you can use: `http://localhost:8889/object_detection_1`

![Vehicle Live Detection](_images/car_live_detection.jpg)
<!--
Expected results:
- Vehicle detection accuracy > 90%
- License plate recognition for clearly visible plates
- Vehicle attribute classification (car, truck, color)
- Real-time processing at 15-30 FPS
- Live video stream with bounding boxes and annotations
-->
## Troubleshooting

### 1. **Container Startup Issues**

If containers fail to start:
```bash
# Check container logs for specific errors
docker logs <container_name>

# Common issues:
# - Port conflicts: Ensure ports 3000, 1880, 8080 are available
# - Permission issues: Verify Docker permissions
# - Resource constraints: Check available memory and disk space
```

### 2. **Model Download Failures**

If model download fails during installation:
```bash
# Retry the installation with verbose output
./install.sh 2>&1 | tee install.log

# Check for network connectivity issues
curl -I https://github.com/openvinotoolkit/open_model_zoo

# Verify disk space
df -h
```

### 3. **Pipeline Processing Errors**

If video processing fails or shows poor accuracy:
```bash
# Check pipeline server logs
docker logs dlstreamer-pipeline-server

# Verify model files are properly installed
ls -la ./crowd-analytics/src/dlstreamer-pipeline-server/models/

# Test with different video source
# Replace the video file with a different sample
```

### 4. **Performance Issues**

For slow processing or high CPU usage:
- **Reduce video resolution**: Use lower resolution input videos
- **Adjust inference device**: Change from CPU to GPU if available
- **Optimize pipeline**: Reduce queue sizes or disable unnecessary features

## Next Steps

After successfully setting up the AI Tolling system, consider these enhancements:

[**Integration with Node Red for enhancing business logic**](./tutorial-2.md)


## Supporting Resources

- [DLStreamer Documentation](https://dlstreamer.github.io/)
- [Metro AI Solutions](https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite)