# How to Run Benchmarking

This guide provides step-by-step instructions for running the benchmarking script to evaluate the performance of the Smart Parking application. The script can help you determine the maximum number of concurrent video streams your system can handle while meeting a specific performance target (e.g., frames per second).

## Overview of the Benchmarking Script

The `benchmark_start.sh` script, located in the `metro-vision-ai-app-recipe` directory, automates the process of running performance tests on the DL Streamer Pipeline Server. It offers two primary modes of operation:

*   **Fixed Stream Mode:** Runs a specified number of concurrent video processing pipelines. This mode is useful for testing a specific, known workload.
*   **Stream-Density Mode:** Automatically determines the maximum number of streams that can be processed while maintaining a target Frames Per Second (FPS). This is ideal for capacity planning and finding the performance limits of your hardware.

## Prerequisites

Before running the benchmarking script, ensure you have the following:

*   A successful deployment of the Smart Parking application using Helm, as described in the [How to Deploy with Helm](./how-to-deploy-with-helm.md) guide.
*   The `jq` command-line JSON processor must be installed. You can install it on Ubuntu with:
    ```bash
    sudo apt-get update && sudo apt-get install -y jq
    ```
*   The `benchmark_start.sh` script and a payload configuration file must be available on your system.

## Understanding the Payload File

The benchmarking script requires a JSON payload file to configure the pipelines that will be tested. These payload files are located within each sample application's directory (e.g., `smart-parking/`). The script uses this file to specify the pipeline to run and the configuration for the video source, destination, and parameters.

Here is an example of a payload file, `benchmark_gpu_payload.json`:

```json
[
    {
        "pipeline": "smart_parking_benchmarking",
        "payload":{
            "parameters": {
                "detection-properties": {
                    "model": "/home/pipeline-server/models/public/yolov10s/FP16/yolov10s.xml",
                    "device": "GPU",
                    "batch-size": 8,
                    "model-instance-id": "instgpu0",
                    "inference-interval": 3,
                    "inference-region": 0,
                    "nireq": 2,
                    "ie-config": "NUM_STREAMS=2",
                    "pre-process-backend": "va-surface-sharing",
                    "threshold": 0.7
                },
                "classification-properties": {
                    "model": "/home/pipeline-server/models/colorcls2/colorcls2.xml",
                    "device": "GPU",
                    "model-instance-id": "instgpu1",
                    "inference-interval": 3,
                    "batch-size": 8,
                    "nireq": 2,
                    "ie-config": "NUM_STREAMS=2",
                    "pre-process-backend": "va-surface-sharing"
                }
            }
        }
    }
]
```

*   `pipeline`: The name of the pipeline to execute (e.g., `smart_parking_benchmarking`).
*   `payload`: An object containing the configuration for the pipeline instance.
    *   `parameters`: Allows you to set pipeline-specific parameters, such as the `detection-device` (CPU, GPU, or NPU) and other model-related properties.

## Step 1: Configure the Benchmarking Script

Before running the script, you may need to adjust the `DLSPS_NODE_IP` variable within `benchmark_start.sh` if your DL Streamer Pipeline Server is not running on `localhost`.

```bash
# Edit the benchmark_start.sh script if needed
nano benchmark_start.sh
```

Change `DLSPS_NODE_IP="localhost"` to the correct IP address of the node where the service is exposed.

## Step 2: Run the Benchmarking Script

The script can be run in two different modes.

Navigate to the `metro-vision-ai-app-recipe` directory to run the script.

```bash
cd edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/
```

### Fixed Stream Mode

In this mode, you specify the exact number of pipelines to run concurrently. This is useful for simulating a known workload.

**To run 4 pipelines simultaneously using the CPU payload:**

```bash
./benchmark_start.sh -p smart-parking/benchmark_cpu_payload.json -n 4
```

*   `-p smart-parking/benchmark_cpu_payload.json`: Specifies the path to your payload configuration file.
*   `-n 4`: Sets the number of concurrent pipelines to run.

The script will start the 4 pipelines and print their status. You can then monitor their performance via Grafana, by using the pipeline status API endpoint, or by running the `./sample_status.sh` script from the `metro-vision-ai-app-recipe` directory to check the average FPS.

### Stream-Density Mode

In this mode, the script automatically finds the maximum number of streams that can run while maintaining a target FPS. This is useful for determining the capacity of your system.

**To find the maximum number of streams that can achieve at least 28.5 FPS on CPU:**

```bash
./benchmark_start.sh -p smart-parking/benchmark_cpu_payload.json -t 28.5
```

*   `-p smart-parking/benchmark_cpu_payload.json`: Specifies the path to your payload configuration file.
*   `-t 28.5`: Sets the target average FPS per stream. The default is `28.5`.
*   `-i 60`: (Optional) Sets the monitoring interval in seconds for collecting FPS data. The default is `60`.

The script will start with one stream, measure the FPS, and if the target is met, it will stop, add another stream, and repeat the process. This continues until the average FPS drops below the target. The script will then report the maximum number of streams that successfully met the performance goal.

**Example Output:**

```
======================================================
✅ FINAL RESULT: Stream-Density Benchmark Completed!
   Maximum 4 stream(s) can achieve the target FPS of 28.5.
======================================================
```

### How Stream Performance is Evaluated

In Stream-Density Mode, the script evaluates if the system can sustain a target FPS across all concurrent streams. The process is as follows:

1.  **Individual Stream Monitoring:** The script monitors each running pipeline instance (stream) independently.
2.  **Sampling:** For the duration of the monitoring interval (e.g., 60 seconds), it samples the `avg_fps` value from each stream every 2 seconds.
3.  **Averaging per Stream:** After the interval, it calculates the average FPS for *each stream* based on the samples collected for that specific stream.
4.  **Validation:** The performance goal is considered met only if **every single stream's** calculated average FPS is greater than or equal to the target FPS. If even one stream falls below the target, the test fails for that number of concurrent streams.

This ensures that the reported optimal stream count represents a stable configuration where all streams are performing adequately, rather than relying on a combined average that could hide underperforming streams.

## Step 3: Stop the Benchmarking

To stop the pipelines, run the `sample_stop.sh` script from the `metro-vision-ai-app-recipe` directory.

```bash
./sample_stop.sh
```

This script will stop all running pipelines that were initiated by the benchmark script.

## Summary

In this guide, you learned how to use the `benchmark_start.sh` script to run performance tests on your Smart Parking application. You can now measure performance for a fixed number of streams or automatically determine the maximum stream density your system can support.
