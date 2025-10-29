# How to Benchmark Performance

This document provides instructions on how to run performance benchmarks for the Vision AI applications using the provided benchmarking scripts. The script determines the maximum number of concurrent video streams a system can process (stream density) while maintaining a target performance level.

## Prerequisites

- The `edge-ai-suites` repository must be cloned to your system.

## Step 1: Understand the Benchmarking Script

The core of the benchmarking process is the `benchmark_start.sh` script, located in the `metro-vision-ai-app-recipe/` directory. This script automates the process of starting video streams, monitoring their performance (Frames Per Second - FPS), and calculating key performance indicators (KPIs) to find the maximum sustainable stream density.

### Stream Density Logic

The script uses a binary search algorithm to efficiently find the optimal stream count within a given range (`lower_bound` and `upper_bound`). Here is a summary of the logic from the `benchmark_start.sh` script:

1.  **Initialization:** The script starts with a lower bound (`lns`) and an upper bound (`uns`) for the number of streams. The current number of streams to test (`ns`) is initialized to the lower bound. A variable (`tns`) tracks the highest successful stream count found so far.

2.  **Binary Search Loop:** The script iterates until the range between the lower and upper bounds is 1, and both bounds have been tested. In each iteration:
    *   It runs a workload with the current number of streams (`ns`).
    *   It measures the `throughput min` (the lowest FPS achieved among all streams) and compares it to the `target_fps`.

3.  **Adjusting the Range:**
    *   **If Performance Target is NOT Met** (`throughput min` < `target_fps`): The current stream count (`ns`) is too high. It becomes the new upper bound (`uns = ns`). The next stream count to test is calculated as the midpoint between the old lower bound and this new upper bound.
    *   **If Performance Target is Met** (`throughput min` >= `target_fps`): The system can handle this workload. The current stream count (`ns`) becomes the new lower bound (`lns = ns`), and the highest successful stream count (`tns`) is updated. The next stream count to test is calculated as the midpoint between this new lower bound and the old upper bound.

4.  **Convergence:** This process of testing midpoints and narrowing the search range continues until the loop condition is met. The final value of `tns` represents the highest number of streams that successfully met the performance target, which is reported as the final stream density.

### Average FPS Calculation

During each test run, the script logs the `avg_fps` for every active pipeline instance at regular intervals. At the end of the run, an `awk` script processes these logs to calculate several KPIs for the collection of FPS samples from each stream:

-   **Percentile Throughput:** Calculates a specific percentile (e.g., 90th) of the FPS values to ignore outliers.
-   **Average Throughput:** The mean FPS across all streams.
-   **Median Throughput:** The median FPS value.
-   **Cumulative Throughput:** The sum of the FPS from all streams.
-   **Min Throughput:** The lowest (worst-case) FPS achieved among all streams. This value is critical for the stream density calculation.

## Step 2: Prepare for Benchmarking

1.  **Set Up and Start the Application:** Before running the benchmark, you must set up and start the desired application (e.g., Smart Parking). This ensures all services, including the DL Streamer Pipeline Server, are running and available. For setup instructions, please refer to the `get-started.md` guide located in the specific application's documentation folder (e.g., `smart-parking/docs/user-guide/`).

2.  **Navigate to Script Directory:** Open a terminal and navigate to the `metro-vision-ai-app-recipe` directory.

    ```bash
    cd edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/
    ```

3.  **Stop Existing Pipelines:** Ensure no other pipelines are running before you start the benchmark. You can stop any running pipelines with the `sample_stop.sh` script.

    ```bash
    ./sample_stop.sh
    ```

## Step 3: Run the Benchmark

The `benchmark_start.sh` script requires a pipeline name and stream count boundaries to run. The available pipelines are defined in the `benchmark_app_payload.json` file located within each application's directory (e.g., `smart-parking/`).

### Example: Running Stream Density Benchmark for Smart Parking

This example will find the maximum number of smart parking streams that can run on the CPU while maintaining at least 15 FPS.

1.  Execute the `benchmark_start.sh` script, providing the desired pipeline name (`object_tracking_cpu` in this case). Here, we test a range of 1 to 16 streams.

    ```bash
    # Usage: ./benchmark_start.sh -p <pipeline_name> -l <lower_bound> -u <upper_bound> -t <target_fps>
    
    ./benchmark_start.sh -p object_tracking_cpu -l 1 -u 16 -t 15
    ```

2.  The script will output its progress as it tests different stream counts. The final output will show the optimal stream density found.

    ```text
    ✅ FINAL RESULT: Stream-Density Benchmark Completed!
    stream density: 8
    ======================================================
    
    KPIs for the optimal configuration (8 streams):
    throughput #1: 29.98
    throughput #2: 29.98
    ...
    throughput #8: 29.98
    throughput median: 29.98
    throughput average: 29.98
    throughput stdev: 0
    throughput cumulative: 239.84
    throughput min: 29.98
    ```

## Step 4: Stop the Benchmark

After the benchmark is complete, or if you need to stop it manually, use the `sample_stop.sh` script. This will delete all running pipeline instances.

```bash
./sample_stop.sh
```