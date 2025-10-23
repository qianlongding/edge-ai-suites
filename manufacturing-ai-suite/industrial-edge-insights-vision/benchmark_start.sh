#!/bin/bash

awk_utils='
  function calc_median(values ,n,v_sorted) {
    if (length(values)==0) return 0
    n=asort(values,v_sorted,"@val_num_asc")
    return v_sorted[(n%2 == 0)?n/2:(n+1)/2]
  }
  function calc_median_if_matched(vt,m,vl ,i,tmp,ct) {
    ct=0
    split("",tmp)
    for (i in vt) if (vt[i]==m) tmp[++ct]=vl[i]
    return calc_median(tmp)
  }
  function calc_sum(values, m,i,nv) {
    m=0
    for (i in values)
      m=m+values[i]
    return m
  }
  function calc_avg(values, m,i,nv) {
    nv=length(values)
    return (nv>0?calc_sum(values)/nv:0)
  }
  function calc_min(values, m,i) {
    m=length(values)>0?values[1]:0
    for (i in values)
      if (values[i]<m) m=values[i]
    return m
  }
  function calc_max(values, m,i) {
    m=0
    for (i in values)
      if (values[i]>m) m=values[i]
    return m
  }
  function calc_stdev(values, nv,i,mean,sum_sq_diff,variance) {
    nv=length(values)
    if (nv<=1) return 0
    mean = calc_avg(values)
    sum_sq_diff = 0
    for (i=1;i<=nv;i++)
      sum_sq_diff+=(values[i]-mean)^2
    return sqrt(sum_sq_diff/(nv-1))
  }
'

DLSPS_NODE_IP="localhost"

function get_pipeline_status() {
    curl -k -s "https://$DLSPS_NODE_IP/api/pipelines/status" "$@"
}

function run_pipelines() {
  local num_pipelines=$1
  local payload_data=$2
  local pipeline_name=$3

  echo >&2
  echo -n ">>>>> Initialization: Starting $num_pipelines pipeline(s) of type '$pipeline_name'..." >&2
  
  for (( x=1; x<=num_pipelines; x++ )); do
    # Create unique payload by modifying peer-id or path for each pipeline instance
    local unique_payload
    local stream_index=$((x-1))
    
    # Generate unique payload to avoid peer-ID conflicts
    unique_payload=$(echo "$payload_data" | jq --arg i "$stream_index" '
      if .destination.frame.path then 
        .destination.frame.path += $i 
      elif .destination.frame["peer-id"] then 
        .destination.frame["peer-id"] += $i 
      else 
        . 
      end')

    response=$(curl -k -s "https://$DLSPS_NODE_IP/api/pipelines/user_defined_pipelines/${pipeline_name}" \
      -X POST -H "Content-Type: application/json" -d "$unique_payload" >/dev/null)
    
    if [ $? -ne 0 ] || [[ "$response" == *"Error"* ]]; then
      echo -e "\nError: curl command failed or pipeline returned error. Check the deployment status." >&2
      echo "Response: $response" >&2
      return 1
    fi
    sleep 1 # Brief pause between requests
  done
  
  # Wait for all pipelines to be in RUNNING state
  echo -n ">>>>> Waiting for pipelines to initialize..." >&2
  local running_count=0
  local attempts=0
  while [ "$running_count" -lt "$num_pipelines" ] && [ "$attempts" -lt 60 ]; do
    status_output=$(get_pipeline_status)
    running_count=$(echo "$status_output" | jq '[.[] | select(.state=="RUNNING")] | length')
    
    echo -n "." >&2
    attempts=$((attempts + 1))
    sleep 2
  done
  
  if [ "$running_count" -ge "$num_pipelines" ]; then
    echo " All pipelines are running." >&2
    return 0
  else
    echo " Error: Not all pipelines entered RUNNING state." >&2
    get_pipeline_status | jq . >&2
    return 1
  fi
}

function stop_all_pipelines() {
  echo >&2
  echo ">>>>> Attempting to stop all running pipelines." >&2
  
  local pipelines_str
  pipelines_str=$(get_pipeline_status | jq -r '[.[] | select(.state=="RUNNING") | .id] | join(",")')
  
  if [ $? -ne 0 ]; then
    echo -e "\nError: Failed to get pipeline status." >&2
    return 1
  fi

  if [ -z "$pipelines_str" ]; then
    echo "No running pipelines found." >&2
    return 0
  fi

  IFS=',' read -ra pipelines <<< "$pipelines_str"
  
  echo "Found ${#pipelines[@]} running pipelines to stop." >&2

  for pipeline_id in "${pipelines[@]}"; do
    curl -k -s --location -X DELETE "https://$DLSPS_NODE_IP/api/pipelines/${pipeline_id}" &
  done
  
  wait
  echo "All stop requests sent." >&2
  unset IFS

  echo -n ">>>>> Waiting for all pipelines to stop..." >&2
  local running=true
  while $running; do
    echo -n "." >&2
    local status
    status=$(get_pipeline_status | jq '.[] | .state' | grep "RUNNING")
    if [[ -z "$status" ]]; then
      running=false
    else
      sleep 3
    fi
  done
  echo " done." >&2
  echo >&2
  return 0
}

function run_and_analyze_workload() {
    local num_streams=$1

    # NOTE: To convert to a full orchestrator, add 'docker compose up' here.
    rm -rf "benchmark-$num_streams" && mkdir -p "benchmark-$num_streams"

    local pipeline_name
    pipeline_name=$(jq -r '.[0].pipeline' "$payload_file")
    local payload_body
    payload_body=$(jq '.[0].payload' "$payload_file")

    run_pipelines "$num_streams" "$payload_body" "$pipeline_name"
    if [ $? -ne 0 ]; then
      echo "Failed to start pipelines. Aborting." >&2
      return 1
    fi

    echo ">>>>> Monitoring FPS for $MAX_DURATION seconds..." >&2
    local start_time=$SECONDS
    while (( SECONDS - start_time < MAX_DURATION )); do
        local elapsed_time=$((SECONDS - start_time))
        echo -ne "Monitoring... ${elapsed_time}s / ${MAX_DURATION}s\r" >&2
        get_pipeline_status > "benchmark-$num_streams/sample.logs" 2>/dev/null
        sleep 1
    done
    echo -ne "\n" >&2

    stop_all_pipelines

    # NOTE: To convert to a full orchestrator, add 'docker compose down' here.
    gawk -v ns=$num_streams "$awk_utils"'
    /^\[/ {
      split("",fps_running)
      ns_running=0
    }
    /"avg_fps":/ {
      fps=$2*1
    }
    /"state": "RUNNING"/ {
      fps_running[++ns_running]=fps
    }
    /^\]/ && ns_running==ns {
      for (i=1;i<=ns;i++)
        throughput[i][++throughput_ct[i]]=fps_running[i]
    }
    END {
      ns=length(throughput)
      if (ns>0) {
        ns1=0
        for (i=1;i<=ns;i++) {
          throughput_med[i]=calc_median(throughput[i])
          if (throughput_med[i]>0) {
            throughput_std[i]=calc_stdev(throughput[i])
            print "throughput #"i": "throughput_med[i]
            ns1++
          }
        }
        print "throughput median: "calc_median(throughput_med)
        print "throughput average: "calc_avg(throughput_med)
        print "throughput stdev: "calc_max(throughput_std)
        print "throughput cumulative: "calc_sum(throughput_med)
        mm=(ns1<ns)?0:calc_min(throughput_med)
        print "throughput median-min: "mm
      }
    }
  ' "benchmark-$num_streams/sample.logs" > "benchmark-$num_streams/kpi.txt"
}

run_workload_with_retries () {
  local num_streams=$1
  local throughput=0
  local retry_ct=0
  local stdev
  while [ $retry_ct -lt ${RETRY_TIMES:-1} ]; do
    echo "Invoking workload with $num_streams streams...try#$retry_ct" >&2
    run_and_analyze_workload "$num_streams" >/dev/null 2>&1 || break
    sed "s|^|stream-density#$num_streams: |" "benchmark-$num_streams/kpi.txt" >&2
    throughput=$(grep -m1 -F 'throughput median-min:' "benchmark-$num_streams/kpi.txt" | cut -f2 -d: | tr -d ' ')
    echo "${throughput:-0} ${target_fps}" | gawk '{exit($1<$2?0:1)}' || break
    stdev=$(grep -m1 -F 'throughput stdev:' "benchmark-$num_streams/kpi.txt" | cut -f2 -d: | tr -d ' ')
    echo "${stdev:-${RETRY_STDEV:-0}} ${RETRY_STDEV:-0}" | gawk '{exit($1>=$2?0:1)}' || break
    let retry_ct++
  done
  echo "$throughput"
}

# --- Main Script ---

function usage() {
    echo "Usage: $0 -p <payload_file> -l <lower_bound> -u <upper_bound> [-t <target_fps>] [-i <interval>]"
    echo
    echo "Arguments:"
    echo "  -p <payload_file>    : (Required) Path to the benchmark payload JSON file."
    echo "  -l <lower_bound>     : (Required) The starting lower bound for the number of streams."
    echo "  -u <upper_bound>     : (Required) The starting upper bound for the number of streams."
    echo "  -t <target_fps>      : Target FPS for stream-density mode (default: 28.5)."
    echo "  -i <interval>        : Monitoring duration in seconds for each test run (default: 60)."
    exit 1
}

payload_file=""
target_fps="28.5"
MAX_DURATION=60
lower_bound=""
upper_bound=""

while getopts "p:l:u:t:i:" opt; do
  case ${opt} in
    p ) payload_file=$OPTARG ;;
    l ) lower_bound=$OPTARG ;;
    u ) upper_bound=$OPTARG ;;
    t ) target_fps=$OPTARG ;;
    i ) MAX_DURATION=$OPTARG ;;
    \? ) usage ;;
  esac
done

if [ -z "$payload_file" ] || [ -z "$lower_bound" ] || [ -z "$upper_bound" ]; then
    echo "Error: Payload file, lower bound, and upper bound are required." >&2
    usage
fi

if [ ! -f "$payload_file" ]; then
    echo "Error: Benchmark payload file not found: $payload_file" >&2
    exit 1
fi

echo ">>>>> Performing pre-flight checks..." >&2
if ! curl -k -s --fail "https://$DLSPS_NODE_IP/api/pipelines/status" > /dev/null; then
    echo "Error: DL Streamer Pipeline Server is not running or not reachable at https://$DLSPS_NODE_IP" >&2
    exit 1
fi
echo "DLSPS is reachable." >&2

stop_all_pipelines
if [ $? -ne 0 ]; then
   exit 1
fi

records=""
ns=$lower_bound
tns=0
lns=$lower_bound
uns=$upper_bound

[[ "$@" = *"--trace"* && $lns -lt $uns ]] || echo "Start-Trace:"
while [ $((uns)) -gt $((lns)) ]; do
  ns=$(( (lns + uns + 1) / 2 ))
  if [[ "$records" = *" $ns:"* ]]; then
    throughput=${records##* $ns:}
    throughput=${throughput%% *}
  else
    throughput=$(run_workload_with_retries $ns 2>/dev/null)
  fi
  records="$records $ns:$throughput"

  echo "streams: $ns throughput: $throughput range: [$lns,$uns]"

  if [ "$(echo "${throughput:-0} >= $target_fps" | bc)" -eq 1 ]; then
    lns=$ns
  else
    uns=$((ns - 1))
  fi
done
tns=$lns

if [[ "$@" = *"--trace"* && $lns -lt $uns ]]; then
  echo "Start-Trace:"
  throughput=$(run_workload_with_retries $tns)
fi
echo "Stop-Trace:"

echo
echo "======================================================" >&2
if [ "$tns" -gt 0 ]; then
    echo "✅ FINAL RESULT: Stream-Density Benchmark Completed!" >&2
    # The primary result goes to stdout
    echo "stream density: $tns"
    echo "======================================================" >&2
    echo >&2
    echo "KPIs for the optimal configuration ($tns streams):" >&2
    # The KPI details go to stdout
    cat "benchmark-$tns/kpi.txt" 2> /dev/null
else
    echo "❌ FINAL RESULT: Target FPS Not Achievable in the given range." >&2
    echo "======================================================" >&2
fi
