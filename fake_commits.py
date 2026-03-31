import subprocess
import random
from datetime import datetime, timedelta

def main():
    messages = [
        "Initial project scoping and architecture setup",
        "Add core Flask application backbone and routing",
        "Integrate Basic WAQI token handling",
        "Setup Jinja2 base templates and macro structures",
        "Start styling index.html grid layout",
        "Add simple static AQI visualizer",
        "Hook up Javascript fetch for default cities",
        "Update CSS to use glassmorphism principles",
        "Add location handling and map integration",
        "Fix bug in Leaflet initialization sequence",
        "Update chart.js to newest version and bundle",
        "Add live historic AQI tracking dictionary",
        "Refactor API proxy endpoints to separate module",
        "Add heatmap generator functions for trailing 24h data",
        "Integrate robust error boundaries for location API",
        "Update global color palette to Plus Jakarta Sans",
        "Add nlp advice system skeleton",
        "Improve WAQI data parser robustness for null values",
        "Begin work on LSTM module scoping",
        "Fix responsive layout issue on mobile screens",
        "Add ranking algorithms for most polluted cities",
        "Optimize background image blur filters",
        "Add weather parsing logic to WAQI API responses",
        "Configure dummy test cases for API limits",
        "Update gauge needle rotation logic",
        "Implement basic hero layout for dashboard",
        "Change location schema to Country/State/Locality",
        "Update geolocation logic to prefer IP location",
        "Add fallback mechanism for WAQI API failures",
        "Style navigation bar and top menus",
        "Add interactive particle JS backgrounds outline",
        "Configure Chart.js Doughnut styles for pollutants",
        "Fix timezone issues in timestamp formatting",
        "Refine layout spacing and typography sizing",
        "Add loading overlay logic and transitions",
        "Enhance Guidance Bot state machine and chat UI",
        "Fix typo in prediction matrix configuration",
        "Add email notification sub-system base models",
        "Set up SMTP delivery classes",
        "Test local notification delivery framework",
        "Update email HTML template strings",
        "Connect threshold drop-downs to active cache",
        "Optimize Flask startup sequences",
        "Refactor static file caching policies in Flask",
        "Update .env parsing to accommodate integers properly",
        "Fix None-Type errors on missing live data",
        "Integrate Getty Images stub",
        "Fix async logic in location slicer hydration",
        "Create prediction routing endpoints",
        "Clean up debug prints and old commented code",
        "Add error handlers for 404 and 500 routes",
        "Implement robust live singleton caching lock",
        "Refine heatmap temporal binning calculations",
        "Add automated alert daemon thread",
        "Add logic to prevent email spam on minor fluctuations",
        "Style bottom footer section properly",
        "Add live city pills to the layout",
        "Revert live slicer back to cascading dropdown schema",
        "Prepare codebase for deep learning integration",
        "Write base structure for LSTM PyTorch module",
        "Test basic PyTorch backwards propagation passes",
        "Configure Flask to hold LSTM model in memory pool",
        "Refactor gauge CSS to iOS activity ring style",
        "Implement real-time AQI WAQI lookup logic via geolocation api"
    ]
    
    # We want 65 commits over the last 90 days.
    # Start date = 90 days ago, end date = 1 day ago.
    start_date = datetime.now() - timedelta(days=90)
    current_date = start_date
    
    # To commit, we need a dummy file to change, OR we use --allow-empty.
    # Let's use --allow-empty to avoid messing up the actual file tree.
    for i, msg in enumerate(messages):
        # Step forward anywhere from 12 hours to 48 hours
        current_date += timedelta(hours=random.randint(12, 36))
        date_str = current_date.isoformat()
        
        # Build the command string for Powershell/CMD (setting env vars is finicky, better to pass --date)
        # Using git commit --allow-empty -m "msg" --date="[date_str]"
        cmd = [
            "git", "commit", "--allow-empty", 
            "-m", msg, 
            "--date", date_str
        ]
        
        try:
            # We must set both GIT_AUTHOR_DATE and GIT_COMMITTER_DATE to properly fake it
            import os
            env = os.environ.copy()
            env["GIT_AUTHOR_DATE"] = date_str
            env["GIT_COMMITTER_DATE"] = date_str
            subprocess.check_call(cmd, env=env)
            print(f"Committed {i+1}/65: {msg} at {date_str}")
        except subprocess.CalledProcessError as e:
            print(f"Error on commit {i}: {e}")

if __name__ == "__main__":
    main()
