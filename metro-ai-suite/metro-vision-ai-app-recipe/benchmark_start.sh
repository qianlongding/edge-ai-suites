#!/bin/bash

DLSPS_NODE_IP="localhost"

function get_pipeline_status() {
    curl -k -s "https://$DLSPS_NODE_IP/api/pipelines/status"
}

function run_pipelines() {
  local num_pipelines=$1
  local payload_data=$2
  local pipeline_name=$3

  echo
  echo -n ">>>>> Initialization: Starting $num_pipelines pipeline(s) of type '$pipeline_name'..."
  
  for (( x=1; x<=num_pipelines; x++ )); do
    response=$(curl -k -s "https://$DLSPS_NODE_IP/api/pipelines/user_defined_pipelines/${pipeline_name}" \
      -X POST -H "Content-Type: application/json" -d "$payload_data")
    
    if [ $? -ne 0 ] || [[ "$response" == *"Error"* ]]; then
      echo -e "\nError: curl command failed or pipeline returned error. Check the deployment status."
      echo "Response: $response"
      return 1
    fi
    sleep 1 # Brief pause between requests
  done
  
  # Wait for all pipelines to be in RUNNING state
  echo -n ">>>>> Waiting for pipelines to initialize..."
  local running_count=0
  local attempts=0
  while [ "$running_count" -lt "$num_pipelines" ] && [ "$attempts" -lt 60 ]; do
    status_output=$(get_pipeline_status)
    running_count=$(echo "$status_output" | jq '[.[] | select(.state=="RUNNING")] | length')
    
    echo -n "."
    attempts=$((attempts + 1))
    sleep 2
  done
  
  if [ "$running_count" -ge "$num_pipelines" ]; then
    echo " All pipelines are running."
    return 0
  else
    echo " Error: Not all pipelines entered RUNNING state."
    get_pipeline_status | jq
    return 1
  fi
}

function stop_all_pipelines() {
  echo
  echo ">>>>> Attempting to stop all running pipelines."
  
  local pipelines_str
  pipelines_str=$(get_pipeline_status | jq -r '[.[] | select(.state=="RUNNING") | .id] | join(",")')
  
  if [ $? -ne 0 ]; then
    echo -e "\nError: Failed to get pipeline status."
    return 1
  fi

  if [ -z "$pipelines_str" ]; then
    echo "No running pipelines found."
    return 0
  fi

  IFS=',' read -ra pipelines <<< "$pipelines_str"
  
  echo "Found ${#pipelines[@]} running pipelines to stop."

  for pipeline_id in "${pipelines[@]}"; do
    curl -k -s --location -X DELETE "https://$DLSPS_NODE_IP/api/pipelines/${pipeline_id}" &
  done
  
  wait
  echo "All stop requests sent."
  unset IFS

  echo -n ">>>>> Waiting for all pipelines to stop..."
  local running=true
  while $running; do
    echo -n "."
    local status
    status=$(get_pipeline_status | jq '.[] | .state' | grep "RUNNING")
    if [[ -z "$status" ]]; then
      running=false
    else
      sleep 3
    fi
  done
  echo " done."
  echo
  return 0
}

function collect_avg_fps() {
    local duration=${1:-60} # Default duration 60s
    
    local total_fps_sum=0
    local num_samples=0
    local num_streams_at_start=0

    # Get initial number of streams
    local initial_status_output
    initial_status_output=$(get_pipeline_status)
    local initial_fps_list
    initial_fps_list=$(echo "$initial_status_output" | jq -r '[.[] | select(.state=="RUNNING") | .avg_fps] | .[]')
    
    if [ -n "$initial_fps_list" ]; then
        num_streams_at_start=$(echo "$initial_fps_list" | wc -l)
    fi

    if [ "$num_streams_at_start" -eq 0 ]; then
        echo "0"
        return
    fi

    end_time=$((SECONDS + duration))
    while [ $SECONDS -lt $end_time ]; do
        local status_output
        status_output=$(get_pipeline_status)
        
        local current_fps_list
        current_fps_list=$(echo "$status_output" | jq -r '[.[] | select(.state=="RUNNING") | .avg_fps] | .[]')
        
        if [ -n "$current_fps_list" ]; then
            # Sum up FPS from all streams for this snapshot
            local snapshot_total_fps
            snapshot_total_fps=$(echo "$current_fps_list" | paste -sd+ - | bc)
            
            if [ -n "$snapshot_total_fps" ]; then
                total_fps_sum=$(echo "$total_fps_sum + $snapshot_total_fps" | bc)
                num_samples=$((num_samples + 1))
            fi
        fi
        sleep 2
    done

    if [ "$num_samples" -eq 0 ]; then
        echo "0"
        return
    fi

    # Calculate average FPS per stream over the duration
    local avg_fps
    avg_fps=$(echo "scale=2; $total_fps_sum / ($num_samples * $num_streams_at_start)" | bc)
    
    echo "$avg_fps"
}

function run_stream_density_mode() {
    local payload_file=$1
    local target_fps=$2
    local duration=$3
    
    echo ">>>>> Running in Stream-Density Calculation Mode (Target FPS: $target_fps)"
    
    local optimal_streams=0
    local current_streams=1
    
    # Extract pipeline name and payload body from the JSON file
    local pipeline_name
    pipeline_name=$(jq -r '.[0].pipeline' "$payload_file")
    local payload_body
    payload_body=$(jq '.[0].payload' "$payload_file")

    if [ -z "$pipeline_name" ] || [ -z "$payload_body" ]; then
        echo "Error: Could not extract 'pipeline' or 'payload' from $payload_file"
        exit 1
    fi

    while true; do
        echo
        echo "--- Testing with $current_streams stream(s) ---"
        
        run_pipelines "$current_streams" "$payload_body" "$pipeline_name"
        if [ $? -ne 0 ]; then
            echo "Failed to start pipelines. Aborting."
            break
        fi
        
        echo ">>>>> Waiting 10 seconds for stabilization..."
        sleep 10
        
        local avg_fps
        avg_fps=$(collect_avg_fps "$duration")
        
        echo ">>>>> Average FPS per stream: $avg_fps"
        
        if (( $(echo "$avg_fps >= $target_fps" | bc -l) )); then
            echo "✓ Target FPS met with $current_streams stream(s)."
            optimal_streams=$current_streams
            
            stop_all_pipelines
            sleep 5
            
            current_streams=$((current_streams + 1))
        else
            echo "❌ Target FPS not met with $current_streams stream(s)."
            break
        fi
    done
    
    stop_all_pipelines
    
    echo
    echo "======================================================"
    if [ "$optimal_streams" -gt 0 ]; then
        echo "✅ FINAL RESULT: Stream-Density Benchmark Completed!"
        echo "   Maximum $optimal_streams stream(s) can achieve the target FPS of $target_fps."
    else
        echo "❌ FINAL RESULT: Target FPS Not Achievable."
        echo "   No configuration could achieve the target FPS of $target_fps."
    fi
    echo "======================================================"
}

# --- Main Script ---

function usage() {
    echo "Usage: $0 -p <payload_file> [-n <num_pipelines> | -t <target_fps>] [-i <interval>]"
    echo
    echo "Modes:"
    echo "  Fixed Stream Mode: Provide -n to run a specific number of pipelines."
    echo "  Stream-Density Mode: Omit -n and provide -t to find the optimal number of streams."
    echo
    echo "Arguments:"
    echo "  -p <payload_file>    : (Required) Path to the benchmark payload JSON file."
    echo "  -n <num_pipelines>   : Number of pipelines to run."
    echo "  -t <target_fps>      : Target FPS for stream-density mode (default: 28.5)."
    echo "  -i <interval>        : Monitoring interval in seconds for stream-density mode (default: 60)."
    exit 1
}

num_pipelines=""
payload_file=""
target_fps="28.5"
interval=60

while getopts "n:p:t:i:" opt; do
  case ${opt} in
    n ) num_pipelines=$OPTARG ;;
    p ) payload_file=$OPTARG ;;
    t ) target_fps=$OPTARG ;;
    i ) interval=$OPTARG ;;
    \? ) usage ;;
  esac
done

if [ -z "$payload_file" ]; then
    echo "Error: Payload file is required."
    usage
fi

if [ ! -f "$payload_file" ]; then
    echo "Error: Benchmark payload file not found: $payload_file"
    exit 1
fi

stop_all_pipelines
if [ $? -ne 0 ]; then
   exit 1
fi

if [ -n "$num_pipelines" ]; then
    if ! [[ "$num_pipelines" =~ ^[0-9]+$ ]] || [ "$num_pipelines" -le 0 ]; then
        echo "Error: Number of pipelines (-n) must be a positive integer."
        usage
    fi
    
    pipeline_name=$(jq -r '.[0].pipeline' "$payload_file")
    payload_body=$(jq '.[0].payload' "$payload_file")

    if [ -z "$pipeline_name" ] || [ -z "$payload_body" ]; then
        echo "Error: Could not extract 'pipeline' or 'payload' from $payload_file"
        exit 1
    fi
    
    run_pipelines "$num_pipelines" "$payload_body" "$pipeline_name"
    if [ $? -ne 0 ]; then
      exit 1
    fi
    
    echo
    echo ">>>>> $num_pipelines pipeline(s) are running."
    echo ">>>>> Results can be visualized in Grafana at 'https://localhost/grafana'"
    echo ">>>>> Pipeline status can be checked with 'curl -k https://localhost/api/pipelines/status'"

else
    run_stream_density_mode "$payload_file" "$target_fps" "$interval"
fi
