#!/usr/bin/env python3

# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: MIT
 

import subprocess
import json
import sys
#from datetime import datetime, timedelta
import argparse
import os
from enum import Enum
#from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm


class PipelineStatus(Enum):
    """
    Enumeration of possible pipeline execution states.
    
    This enum defines all valid states that a pipeline can be in during its lifecycle
    on the DLStreamer Pipeline Server. Each state represents a distinct phase or condition
    of pipeline execution.
    
    Attributes:
        RUNNING (str): Pipeline is currently actively processing data
        COMPLETED (str): Pipeline has finished execution successfully
        FAILED (str): Pipeline encountered an error and stopped
        PENDING (str): Pipeline is queued but not yet started
        PAUSED (str): Pipeline execution is temporarily suspended
        CANCELLED (str): Pipeline was manually terminated by user
        UNKNOWN (str): Pipeline state cannot be determined or is unrecognized
    """
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    PENDING = 'PENDING'
    PAUSED = 'PAUSED'
    CANCELLED = 'CANCELLED'
    UNKNOWN = 'UNKNOWN'


class DLSPSManager:
    """
    Manager class for interacting with DLStreamer Pipeline Server (DLSPS) REST API.
    This class provides a high-level interface for managing video processing pipelines on a
    DLStreamer Pipeline Server. It handles HTTP communication via curl commands, pipeline
    lifecycle management (start/stop), and provides formatted console output for pipeline
    status and information.
    The manager maintains cached lists of both predefined pipeline templates available on
    the server and currently running pipeline instances. It supports interactive user
    workflows for selecting and managing pipelines through a rich terminal interface.
    Note:
        - All HTTP communication is performed via curl subprocess calls
        - SSL certificate verification is disabled by default (-k flag)
        - Pipeline data is fetched fresh from the server on each display/query operation
    """
    def __init__(self, base_url="https://localhost", api_key=None, timeout=30, verbose=False):
        """
        Initializes a new DLSPSManager instance for managing DLStreamer Pipeline Server.
        
        Args:
            base_url (str, optional): Base URL of the DLStreamer Pipeline Server API.
                                     Defaults to "https://localhost".
            api_key (str|None, optional): API key for authentication (currently unused).
                                         Defaults to None.
            timeout (int, optional): Timeout in seconds for HTTP requests. Defaults to 30.
            verbose (bool, optional): Enable verbose logging output. Defaults to False.
        
        Attributes:
            base_url (str): Normalized base URL without trailing slash
            api_key (str|None): API key for authentication
            timeout (int): Request timeout in seconds
            verbose (bool): Verbose mode flag
            console (Console): Rich Console instance for formatted output
            table_predefined (Table): Rich Table for displaying predefined pipelines
            table_instanced (Table): Rich Table for displaying instanced pipelines
            predefined_pipelines (list): List of available predefined pipelines
            instanced_pipelines (list): List of currently running pipeline instances
        """
        # Remove trailing slash from base URL for consistent endpoint construction
        self.base_url = base_url.rstrip('/')
        
        # API key for authentication (reserved for future use)
        self.api_key = api_key
        
        # Timeout duration for HTTP requests in seconds
        self.timeout = timeout
        
        # Flag to enable/disable verbose logging
        self.verbose = verbose
        
        # Rich Console instance for formatted terminal output
        self.console = Console()

        # Rich Table for displaying predefined pipelines available on server
        self.table_predefined = Table(title="DLSPS Predefined Pipelines", show_header=True, header_style="bold magenta")
        
        # Rich Table for displaying currently running pipeline instances
        self.table_instanced = Table(title="DLSPS Instanced Pipelines", show_header=True, header_style="bold magenta")

        # List to store predefined pipeline configurations from server
        self.predefined_pipelines = []
        
        # List to store active/running pipeline instances
        self.instanced_pipelines = []

    def build_curl_command(self, endpoint, method="GET", path=None, data=None, extra_headers=None):
        """
        Builds a curl command for making HTTP requests to the pipeline server API.
        
        Constructs a complete curl command with proper headers, SSL handling, and data payload
        for interacting with the DLStreamer Pipeline Server REST API.
        
        Args:
            endpoint (str): API endpoint path (e.g., "/api/pipelines")
            method (str, optional): HTTP method to use. Defaults to "GET".
                                   Supports GET, POST, PUT, DELETE, etc.
            path (str, optional): Currently unused. Reserved for future path parameter handling.
            data (dict|str|None, optional): Data to send in the request body. Can be a JSON string
                                           or dict that will be serialized. Defaults to None.
            extra_headers (list|None, optional): Additional HTTP headers to include in the request.
                                                Each header should be a string in "Key: Value" format.
                                                Defaults to None.
        
        Returns:
            list: Complete curl command as a list of string arguments ready for subprocess execution.
                  Includes base URL, method, headers, and any data payload.
        
        Example:
            >>> cmd = self.build_curl_command("/api/pipelines", method="POST", 
            ...                               data='{"name": "test"}')
            >>> # Returns: ['curl', '-k', '--location', '-s', 'https://localhost/api/pipelines', 
            ...             '-X', 'POST', '-H', 'Accept: application/json', ...]
        """
        # Construct the full endpoint URL by combining base URL with the endpoint path
        endpoint = f"{self.base_url}{endpoint}"

        # Build the base curl command with common options
        cmd = [
            'curl',
            '-k',           # Allow insecure SSL connections (skip certificate verification)
            '--location',   # Follow HTTP redirects automatically
            '-s',           # Silent mode - suppress progress meter and error messages
            endpoint,
            '-X', method,   # Specify HTTP method (GET, POST, PUT, DELETE, etc.)
            '-H', "Accept: application/json",        # Request JSON response from server
            '-H', "Content-Type: application/json"   # Indicate JSON content in request body
        ]

        # Add request body data if provided
        if data is not None:
            cmd.extend(['-d', data])

        # Add any additional custom headers if provided
        if extra_headers:
            for header in extra_headers:
                cmd.extend(['-H', header])

        return cmd

    def execute_curl(self, cmd):
        """
        Executes a curl command and returns the parsed JSON response.
        
        This method runs the provided curl command using subprocess, captures the output,
        and attempts to parse it as JSON. It includes comprehensive error handling for
        various failure scenarios.
        
        Args:
            cmd (list): A list of command arguments to pass to subprocess (e.g., ['curl', '-X', 'GET', ...])
        
        Returns:
            dict/list/None: The parsed JSON response from the curl command if successful.
                           Returns None if the request fails, times out, or returns invalid JSON.
        
        Raises:
            No exceptions are raised; all errors are caught and handled internally.
            Error messages are printed to console if verbose mode is enabled.
        
        Error Handling:
            - JSONDecodeError: When response body is not valid JSON
            - CalledProcessError: When curl command returns non-zero exit code
            - TimeoutExpired: When command exceeds self.timeout duration
            - General exceptions: Catches any other unexpected errors
        
        Example:
            >>> cmd = ['curl', '-s', 'https://api.example.com/data']
            >>> response = self.execute_curl(cmd)
            >>> if response:
            ...     print(response)
        """
        result = None

        try:
            # Execute curl command with timeout and capture both stdout and stderr
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=self.timeout)

            # Parse and return the JSON response
            return json.loads(result.stdout)

        except json.JSONDecodeError as e:
            # Handle cases where the response is not valid JSON
            if self.verbose:
                self.console.print(f"JSON parse error: {e}")
                self.console.print(f"Response: {result.stdout[:200]}...")
            return None
        except subprocess.CalledProcessError as e:
            # Handle cases where curl command fails (non-zero exit code)
            if self.verbose:
                self.console.print(f"Subprocess error: {e}")
                self.console.print(f"[red]HTTP request failed: {e.stderr}[/red]")
            return None
        except Exception as e:
            # Catch-all for any other unexpected errors
            if self.verbose:
                self.console.print(f"Curl execution error: {e}")
            return None


    def pipelines_to_be_stopped(self):
        """
        Retrieves a list of pipelines that are currently running and can be stopped.
        
        This method clears the console, fetches all instanced pipelines from the server,
        and filters them to return only those in a RUNNING state.
        
        Returns:
            list: A list of pipeline dictionaries that are currently in RUNNING state.
                  Each dictionary contains pipeline details such as id, state, avg_fps, etc.
                  Returns an empty list if no running pipelines are found.
        
        Side Effects:
            - Clears the console screen
            - Calls get_instanced_pipelines() to refresh pipeline data from server
        
        Example:
            >>> running = manager.pipelines_to_be_stopped()
            >>> print(f"Found {len(running)} running pipelines")
        """

        # Clear the console for better readability
        os.system('clear')
        
        # Fetch the latest list of instanced pipelines from the server
        self.get_instanced_pipelines()

        # Initialize list to store pipelines that are currently running
        running_pipelines = []

        # Filter pipelines to find only those in RUNNING state
        for pipeline in self.instanced_pipelines:
            if pipeline['state'] == PipelineStatus.RUNNING.value:
                running_pipelines.append(pipeline)

        return running_pipelines


    def stop_selected_pipeline(self, pipeline_id: str) -> bool:
        """
        Stops a specific pipeline by its ID.
        
        Sends a DELETE request to the pipeline server to terminate the specified pipeline.
        
        Args:
            pipeline_id (str): The unique identifier of the pipeline to stop.
        
        Returns:
            bool: True if the pipeline was successfully stopped, False otherwise.
                  Returns the result from the DELETE API call.
        
        Example:
            >>> manager.stop_selected_pipeline("pipeline-123")
            True
        """
        endpoint = f"/api/pipelines/{pipeline_id}"
        cmd = self.build_curl_command(endpoint, method="DELETE")
        result = self.execute_curl(cmd)
        return result


    def stop_pipeline(self):
        """
        Allows user to interactively select and stop a running pipeline.
        
        This method displays all currently running pipelines in a formatted table and
        prompts the user to select one to stop. The user can also cancel the operation.
        
        Returns:
            bool or None: Result from stop_selected_pipeline() if a pipeline is stopped,
                         None if cancelled or no pipelines available to stop.
        
        Side Effects:
            - Retrieves current instanced pipelines from server
            - Displays formatted table of running pipelines in console
            - Prompts user for input
            - May stop a selected pipeline
        """

        # Retrieve all currently instanced pipelines from the server
        self.get_instanced_pipelines()
        
        # Filter for only pipelines that are in RUNNING state
        stoppable_pipelines = self.pipelines_to_be_stopped()

        # If no running pipelines exist, inform user and return
        if not stoppable_pipelines:
            self.console.print("[yellow]No pipelines available to be stopped.[/yellow]")
            Prompt.ask("Press Enter to continue...")
            return None

        self.console.print("\n[bold]Pipelines available to be stopped:[/bold]")

        # Create a formatted table to display running pipeline information
        table = Table("No", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="dim")
        table.add_column("State")
        table.add_column("Average FPS")
        table.add_column("Elapsed time")

        # Populate table with each running pipeline's details
        counter: int = 0
        for p in stoppable_pipelines:
            counter += 1
            table.add_row(str(counter), p['id'], p['state'], str(p['avg_fps']), self.format_elapsed_time(p['elapsed_time']))

        # Display the table in the console
        self.console.print(table)

        # Prompt user to select a pipeline by number (1-indexed), or 0 to cancel
        choice = Prompt.ask("Select a pipeline to stop (0 to cancel)", choices=[str(i) for i in range(0, len(stoppable_pipelines)+1)])
        
        # If user selects 0, cancel the operation
        if choice == "0":
            return None

        # Get the selected pipeline (adjust for 1-based indexing)
        selected_pipeline = stoppable_pipelines[int(choice)-1]
        
        # Attempt to stop the selected pipeline and return the result
        return self.stop_selected_pipeline(selected_pipeline['id'])


    def get_predefined_pipelines(self):
        """
        Retrieves the list of predefined pipelines from the DLStreamer Pipeline Server.

        This method sends a GET request to the '/api/pipelines' endpoint to fetch all
        available predefined pipeline configurations from the server. The retrieved
        pipelines are stored in the instance's predefined_pipelines list.

        Returns:
            list: A list of predefined pipeline objects/dictionaries. Each item represents
                  a pipeline configuration available on the server. Returns an empty list
                  if no pipelines are available or if the request fails.

        Example:
            >>> pipelines = instance.get_predefined_pipelines()
            >>> print(f"Found {len(pipelines)} predefined pipelines")
        """
        endpoint = "/api/pipelines"
        cmd = self.build_curl_command(endpoint)
        result = self.execute_curl(cmd)
        self.predefined_pipelines.clear()
        if result and isinstance(result, list):
            for item in result:
                self.predefined_pipelines.append(item)
        return self.predefined_pipelines

    def get_instanced_pipelines(self):
        """
        Retrieves all currently instanced (running) pipelines from the DLStreamer pipeline server.

        This method queries the server's status endpoint to get a list of all active pipeline instances.
        It clears any previously cached pipeline instances and populates the internal list with the
        current state from the server.

        Returns:
            list: A list of dictionaries containing information about each instanced pipeline.
                  Each dictionary contains pipeline instance details such as ID, name, and status.
                  Returns an empty list if no pipelines are running or if the request fails.

        Example:
            >>> pipelines = self.get_instanced_pipelines()
            >>> print(f"Found {len(pipelines)} running pipelines")
        """
        endpoint = "/api/pipelines/status"
        cmd = self.build_curl_command(endpoint)
        result = self.execute_curl(cmd)
        self.instanced_pipelines.clear()
        if result and isinstance(result, list):
            for item in result:
                self.instanced_pipelines.append(item)
        return self.instanced_pipelines

    def start_new_pipeline(self):
        """
        Interactively starts a new pipeline instance from available predefined pipelines.
        
        This method guides the user through the process of starting a new pipeline by:
        1. Displaying available predefined pipelines
        2. Allowing selection of a pipeline to start
        3. Choosing a display window (1-4)
        4. Selecting a processing device (CPU/GPU/NPU)
        5. Sending a POST request to start the pipeline with the configured parameters
        
        Returns:
            bool: True if the pipeline was successfully started, False if cancelled or failed.
        
        Side Effects:
            - Fetches predefined pipelines from server
            - Prompts user for multiple inputs
            - Sends POST request to start pipeline
            - Displays status messages to console
        """
        # Fetch the list of available predefined pipelines from the server
        self.get_predefined_pipelines()
        
        # Check if any predefined pipelines are available
        if not self.predefined_pipelines:
            self.console.print("[yellow]No predefined pipelines available to start.[/yellow]")
            return False
        else:
            self.console.print(f"[green]Found {len(self.predefined_pipelines)} predefined pipelines.[/green]")


        # Display available pipelines to the user
        self.console.print("\n[bold]Available predefined pipelines:[/bold]")

        # Enumerate and display each pipeline with a numbered index
        count: int = 0
        for pipeline in self.predefined_pipelines:
            count += 1
            self.console.print(f"\t[{count}] - {pipeline['version']} ")

        # Prompt user to select a pipeline (or cancel with 0)
        choicePipeline = Prompt.ask("\n\t[bold]Select a pipeline to start (0 to cancel)[/bold]", choices=[str(i) for i in range(0, len(self.predefined_pipelines)+1)])

        # Handle cancellation
        if choicePipeline == "0":
            self.console.print("[red]Pipeline start canceled.[/red]")
            return False

        # Display selected pipeline
        self.console.print(f"\t[green]Selected pipeline pipeline: {self.predefined_pipelines[int(choicePipeline)-1]['version']}[/green]\n")

        # Store the selected pipeline object (adjust for 1-based indexing)
        selected_pipeline = self.predefined_pipelines[int(choicePipeline)-1]

        # Display window selection options (base sample supports 4 display windows)
        for i in range(1, 5):
            self.console.print(f"\t\t[{i}] - Window {i}")

        # Prompt user to select a display window
        choiceWindow = Prompt.ask("\n\t\t[bold]Select window 1-4 to display stream (0 to cancel)[/bold]", choices=[str(i) for i in range(0, 5)])

        # Handle cancellation
        if choiceWindow == "0":
            self.console.print("[red]Pipeline start canceled.[/red]")
            return False

        # Store the selected window ID
        windowId: int = int(choiceWindow)

        # Display device selection options
        device = "CPU"  # Default device
        self.console.print("\n\t\t\t[1] - CPU")
        self.console.print("\t\t\t[2] - GPU")
        self.console.print("\t\t\t[3] - NPU")
        
        # Prompt user to select a processing device
        choiceDevice = Prompt.ask("\n\t\t\t[bold]Select a device to use (0 to cancel)[/bold]", choices=[str(i) for i in range(0, 4)])
        
        # Map user choice to device name
        match choiceDevice:
            case "1":
                device = "CPU"
            case "2":
                device = "GPU"
            case "3":
                device = "NPU"
            case "0" | _:
                # Handle cancellation or invalid choice
                self.console.print("[red]Pipeline start canceled.[/red]")
                return False

        # Construct the API endpoint for starting the selected pipeline
        endpoint = f"/api/pipelines/user_defined_pipelines/{selected_pipeline['version']}"

        # Build the data payload for the pipeline configuration
        # This includes source video URI, destination outputs (MQTT and WebRTC), and processing parameters.
        # It can be customized as needed for different use cases or made dynamic or loaded from config. 
        # Below is just a sample code snippet.
        data = json.dumps({
            "source": {
                "uri": f"file:///home/pipeline-server/videos/new_video_{windowId}.mp4",
                "type": "uri"
            },
            "destination": {
                "metadata": {
                    "type": "mqtt",
                    "topic": f"object_detection_{windowId}",
                    "publish_frame": False
                },
                "frame": {
                    "type": "webrtc",
                    "peer-id": f"object_detection_{windowId}"
                }
            },
            "parameters": {
                "detection-device": f"{device}"
            }
        })

        # Build and execute the curl command to start the pipeline
        cmd = self.build_curl_command(endpoint, method="POST", data=data)
        result = self.execute_curl(cmd)

        # Display success or error message based on the result
        if result:
            self.console.print(f"[green]Successfully started pipeline: {selected_pipeline['version']}[/green]")
        else:
            self.console.print(f"[red]Error: {result}[/red]")

        # Wait for user acknowledgment before continuing
        Prompt.ask("Press Enter to continue...")

        return True

    def show_predefined_pipelines_on_server(self):
        """
        Displays all predefined pipelines available on the DL Streamer Pipeline Server.

        This method retrieves the list of predefined pipelines from the server and presents
        them in a formatted table showing the pipeline name and version. The table is rendered
        to the console using the Rich library.

        The method performs the following steps:
        1. Fetches the current list of predefined pipelines from the server
        2. Creates a new Rich Table with appropriate headers
        3. Populates the table with pipeline name and version information
        4. Displays the formatted table in the console

        Returns:
            None

        Side Effects:
            - Updates self.predefined_pipelines via get_predefined_pipelines()
            - Creates/overwrites self.table_predefined
            - Prints table output to console via self.console.print()
        """
        """Displays pipelines available on the server"""

        # Retrieve current predefined pipelines from the server
        self.get_predefined_pipelines()

        # Create a new/clean table to display predefined pipeline information
        self.table_predefined = Table(title="DLSPS predefined pipelines", show_header=True, header_style="bold magenta")
        self.table_predefined.add_column("Name", style="dim")
        self.table_predefined.add_column("Version", min_width=10)

        # Add each pipeline as a row in the table
        for pipeline in self.predefined_pipelines:
            self.table_predefined.add_row(pipeline['name'], pipeline['version'])

        # Display the table in the console
        self.console.print(self.table_predefined)


    def show_instanced_pipelines_on_server(self):
        """
        Displays currently running pipeline instances from the server.
        
        Retrieves the list of active pipeline instances and displays them in a formatted
        table showing their ID, current state, average FPS, and elapsed running time.
        """

        # Retrieve current instanced pipelines from the server
        self.get_instanced_pipelines()

        # Create a new/clean table to display instanced pipeline information
        self.table_instanced = Table(title="DLSPS instanced pipelines", show_header=True, header_style="bold magenta")
        self.table_instanced.add_column("ID", style="dim")
        self.table_instanced.add_column("State", min_width=10)
        self.table_instanced.add_column("AVR FPS", style="dim")
        self.table_instanced.add_column("Elapsed time", style="dim")

        # Add each pipeline as a row in the table
        for pipeline in self.instanced_pipelines:
            self.table_instanced.add_row(pipeline['id'], pipeline['state'], str(pipeline['avg_fps']), self.format_elapsed_time(pipeline['elapsed_time']))

        # Display the table in the console
        self.console.print(self.table_instanced)


    def format_elapsed_time(self, seconds):
        """
        Formats elapsed time in seconds to a human-readable HH:MM:SS.mmm format.

        Args:
            seconds (float): The elapsed time in seconds to format.

        Returns:
            str: A formatted string in the format "HH:MM:SS.mmm" where:
                - HH: hours (zero-padded to 2 digits)
                - MM: minutes (zero-padded to 2 digits)
                - SS.mmm: seconds with 3 decimal places (zero-padded to 6 total characters)

        Example:
            >>> format_elapsed_time(3661.5)
            '01:01:01.500'
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60

        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

def main():
    """
    Main entry point for the DLStreamer Pipeline Server management application.
    
    This function provides an interactive command-line interface for managing pipelines
    on a DLStreamer Pipeline Server. It supports the following operations:
    - Viewing predefined and instanced pipelines
    - Starting new pipeline instances
    - Stopping running pipelines
    
    The function parses command-line arguments for server URL and verbose mode,
    then enters an interactive menu loop that continues until the user exits.
    
    Command-line Arguments:
        -u, --url: URL of the DLStreamer Pipeline Server (default: https://localhost)
        -v, --verbose: Enable verbose output for debugging
    
    Raises:
        KeyboardInterrupt: When user cancels with Ctrl+C
        Exception: For any unexpected errors during execution
    """

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Pipeline status monitor for DLS PS')
    parser.add_argument('-u', '--url', default='https://localhost',
                       help='URL of the DLS PS server')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose mode')

    args = parser.parse_args()

    # Initialize the DLSPSManager with the provided server URL
    manager = DLSPSManager(base_url=args.url)

    
    # Main interactive loop
    while True:
        try:
            # Clear the console for better readability
            os.system('clear')

            # Display application title/banner        
            manager.console.print("[bold blue]DLStreamer Pipeline Server \nDynamic Pipelines Management Sample[/bold blue]")
            
            # Display menu options to the user
            manager.console.print("\n[bold]Available options:[/bold]")
            manager.console.print("1. Show pipelines on the server")
            manager.console.print("2. Stop pipeline")
            manager.console.print("3. Start pipeline")
            manager.console.print("0. Exit")

            # Prompt user for menu selection
            choice = Prompt.ask("Choose an option", choices=["1", "2", "3", "0"], default="1")

            if choice == "1":
                # Display both predefined pipeline templates and currently running instances
                os.system('clear')
                manager.show_predefined_pipelines_on_server()
                manager.show_instanced_pipelines_on_server()
                Prompt.ask("\n[bold][blue]Press Enter to continue...[/blue][/bold]")
                continue

            elif choice == "2":
                # Interactively stop a running pipeline
                manager.stop_pipeline()
                
            elif choice == "3":
                # Start a new pipeline instance from predefined templates
                os.system('clear')
                manager.start_new_pipeline()
                
            elif choice == "0":
                # Exit the program gracefully
                manager.console.print("[green]Exiting the program.[/green]")
                break

        except KeyboardInterrupt:
            # Handle user cancellation (Ctrl+C)
            print("\nCancelled by user. ")
            sys.exit(1)
            
        except Exception as e:
            # Handle unexpected errors with optional traceback in verbose mode
            print(f"Error: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)

# Entry point of the script
# This conditional ensures that main() is only called when the script is executed directly,
# not when imported as a module in another script
if __name__ == "__main__":
    main()
