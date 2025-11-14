<!-- 
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: MIT
# 
-->

# Dynamic Pipeline Management Sample

## Overview

The Dynamic Pipeline Management sample is an interactive console application that extends the functionality of the [Smart Parking sample](https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-parking) from the Open Edge Platform AI Suites. This tool provides comprehensive pipeline management capabilities through an intuitive command-line interface, enabling users to monitor, start, and stop AI inference pipelines with support for multiple display windows and hardware acceleration options.

### Key Features
- **Interactive Pipeline Management**: Start, stop, and monitor AI inference pipelines in real-time
- **Multi-Window Support**: Deploy streams across 1 to 4 display windows simultaneously  
- **Hardware Flexibility**: Configure pipelines for CPU, GPU, or NPU execution
- **License Plate Detection**: Integrated YOLOv8 license plate recognition capabilities
- **Real-Time Monitoring**: View pipeline status, performance metrics, and resource utilization
- **Dashboard Integration**: All operations are reflected in both the console interface and Smart Parking web dashboard

### Architecture
This sample acts as a management layer for the DLStreamer Pipeline Server, providing:
- REST API communication with the pipeline server
- Rich console interface with formatted tables and interactive prompts  
- Pipeline lifecycle management (create, start, stop, monitor)
- Configuration management for different AI models and hardware targets

## Complete Setup and Getting Started Guide

### Prerequisites
Before beginning, ensure you have:
- Python 3.6+ installed on your system
- Access to the Smart Parking sample environment
- Sufficient hardware resources (CPU/GPU/NPU) for your intended pipeline configurations

### Step 1: Install Dependencies
Install the required Python module:
```bash
pip3 install rich
```

### Step 2: Clone Repository
Download the Edge AI Suites repository:
```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/smart-parking/src/dlstreamer-pipeline-server/samples/dynamic-pipelines
```

### Step 3: Download AI Models
1. **Download the model download script**:
   ```bash
   wget https://github.com/open-edge-platform/edge-ai-libraries/blob/main/libraries/dl-streamer/samples/download_public_models.sh
   chmod +x download_public_models.sh
   ```

2. **Configure model path environment**:
   ```bash
   export MODELS_PATH="$(pwd)/../../models/"
   ```

3. **Download YOLOv8 license plate detector model**:
   ```bash
   ./download_public_models.sh yolov8_license_plate_detector
   ```

### Step 4: Configure Pipeline Definition
Add the license plate detection pipeline configuration to the Smart Parking config file:

**File**: `../../config.json`

Add this configuration to the existing config.json:
```json
{
    "name": "dynamic_pipeline_sample_yolov8_license_plate_detector",
    "source": "gstreamer",
    "queue_maxsize": 50,
    "pipeline": "{auto_source} name=source ! decodebin force-sw-decoders=true ! videoconvert ! video/x-raw ! gvadetect model=/home/pipeline-server/models/yolov8_license_plate_detector/FP32/yolov8_license_plate_detector.xml pre-process-backend=opencv device=CPU threshold=0.7 inference-interval=1 inference-region=0 ! queue ! queue ! gvafpscounter ! videoconvert ! appsink name=destination",
    "parameters": {
        "type": "object",
        "properties": {
            "detection-properties": {
                "element": {
                    "name": "detection",
                    "format": "element-properties"
                }
            },
            "classification-properties": {
                "element": {
                    "name": "classification",
                    "format": "element-properties"
                }
            }
        }
    },
    "auto_start": false
}
```

### Step 5: Verify Smart Parking Sample
Ensure the Smart Parking sample is running and accessible:
- Confirm the DLStreamer Pipeline Server is active
- Verify the Smart Parking dashboard is accessible
- Check that all required models are properly loaded

### Step 6: Launch the Application
Run the dynamic pipeline management interface:
```bash
python3 dynamic-pipelines-sample.py
```

### Step 7: Using the Interface
The application provides an interactive menu with these options:

1. **Show Pipelines on Server** 
   - View all predefined pipeline templates available for deployment
   - Display currently running pipeline instances with real-time metrics
   - Monitor performance data: FPS, elapsed time, resource usage

2. **Stop Pipeline**
   - Select from currently running pipelines
   - Safely terminate pipeline instances
   - Immediate reflection in dashboard

3. **Start Pipeline**
   - Choose from available predefined pipeline configurations
   - Select target display window (1-4)
   - Configure hardware acceleration (CPU/GPU/NPU)
   - Deploy with custom parameters

4. **Exit**
   - Clean application termination

### Verification and Monitoring
**Success Indicators**:
- ✅ Interactive menu displays without errors
- ✅ Pipeline tables populate with current data
- ✅ Operations appear in both console and web dashboard
- ✅ No connection errors to dlstreamer-pipeline-server
- ✅ Video streams display in selected windows

**Performance Monitoring**:
- Real-time FPS metrics for active pipelines
- Resource utilization tracking
- Pipeline state monitoring (RUNNING, STOPPED, FAILED)
- Elapsed time tracking for long-running processes

### Troubleshooting Common Issues

**Connection Issues**:
- Verify Smart Parking sample is running: `docker ps | grep dlstreamer`
- Check pipeline server accessibility: `curl -k https://localhost/api/pipelines`
- Validate network connectivity between components

**Model Issues**:
- Ensure models are in correct path: `ls /home/pipeline-server/models/yolov8_license_plate_detector/`
- Verify model file permissions and accessibility
- Check model format compatibility (XML/BIN files present)

**Configuration Issues**:
- Validate JSON syntax in config.json
- Ensure pipeline configuration matches available models
- Verify device compatibility (GPU/NPU availability)

## Limitations and Platform Compatibility
- **Hardware Dependencies**: GPU and NPU options require compatible hardware and drivers
- **Platform Variations**: Some pipeline configurations may not be available on all platforms
- **Model Requirements**: Specific AI models must be downloaded and configured before use
- **Dependency Chain**: Smart Parking sample must be running as a prerequisite

## Integration Notes
This sample integrates with:
- **Smart Parking Dashboard**: All pipeline operations are reflected in the web interface
- **DLStreamer Pipeline Server**: Direct REST API communication for pipeline management  
- **Intel OpenVINO**: Utilizes optimized inference engines for various hardware targets
- **Docker Environment**: Operates within the Smart Parking containerized environment


---
*Part of the [Edge AI Suites](https://github.com/open-edge-platform/edge-ai-suites) project.*